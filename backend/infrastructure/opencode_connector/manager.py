import asyncio
import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional, Callable, Awaitable
from datetime import datetime
from backend.transport.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

def _opencode_cmd() -> str:
    """Retourne le nom de la commande opencode selon la plateforme."""
    return "opencode.cmd" if sys.platform == "win32" else "opencode"

class OpenCodeConnectorManager:
    """
    Connector OpenCode. Délègue des tâches à OpenCode via le CLI
    en mode headless (opencode run --format json).
    """
    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None
        self.project_path: Optional[str] = None
        self._output_buffer = ""
        self._callbacks: List[Callable[[Dict], Awaitable[None]]] = []
        self._notification_history: List[Dict] = []
        self._max_history = 100

    async def start(self, project_path: str, model: str = "lmstudio/google/gemma-4-12b-qat"):
        """Démarre OpenCode sur un projet (mode interactif)."""
        self.project_path = project_path
        cmd = [_opencode_cmd(), "--model", model, "--project", project_path, "--verbose"]
        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE, cwd=project_path,
            )
            logger.info(f"OpenCode démarré pour {project_path} avec {model}")
            asyncio.create_task(self._stream_output())
            return True
        except FileNotFoundError:
            logger.error("OpenCode CLI non trouvé. Installez-le via https://opencode.ai")
            return False

    async def _stream_output(self):
        """Lit la sortie en temps réel et notifie les callbacks (WebSocket)."""
        if not self.process or not self.process.stdout:
            return

        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            text = line.decode('utf-8').strip()
            self._output_buffer += text + "\n"

            # Détection de patterns utiles
            event = None
            if "FILE:" in text:
                event = {"type": "file_update", "content": text, "priority": "high"}
            elif "ERROR" in text or "Exception" in text:
                event = {"type": "error", "content": text, "priority": "critical"}
            elif "SUCCESS" in text:
                event = {"type": "success", "content": text, "priority": "medium"}
            elif re.search(r'\.(py|ts|js|html|css)$', text):
                event = {"type": "token", "content": text, "priority": "low"}

            if event:
                await self._notify(event)

    async def send_task(self, task: str) -> bool:
        """Envoie une tâche à OpenCode"""
        if not self.process or not self.process.stdin:
            return False

        try:
            self.process.stdin.write((task + "\n").encode())
            await self.process.stdin.drain()
            logger.info(f"Tâche envoyée à OpenCode: {task[:100]}...")
            return True
        except Exception as e:
            logger.error(f"Erreur envoi tâche OpenCode: {e}")
            return False

    async def run(self, task: str, project_path: str = ".",
                  model: str = "lmstudio/google/gemma-4-12b-qat") -> Dict[str, Any]:
        """Exécute une tâche via opencode run --format json."""
        cmd = [
            _opencode_cmd(), "run", task, "--format", "json",
            "--model", model, "--port", "0", "--pure",
        ]
        logger.debug(f"Running: {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, cwd=project_path,
            )

            response_parts: List[str] = []
            session_id: str = ""
            success = False

            async def read_stdout():
                nonlocal session_id, success
                assert proc.stdout is not None
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    try:
                        event = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError:
                        continue

                    if event.get("type") == "text":
                        response_parts.append(event.get("part", {}).get("text", ""))
                    elif event.get("type") == "step_finish":
                        success = True
                    elif event.get("type") == "error":
                        logger.error(f"OpenCode error: {event.get('error', {})}")
                        success = False
                        return
                    sid = event.get("sessionID")
                    if sid:
                        session_id = sid

            async def read_stderr():
                assert proc.stderr is not None
                while True:
                    line = await proc.stderr.readline()
                    if not line:
                        break
                    text = line.decode("utf-8").strip()
                    if text:
                        logger.debug(f"[opencode stderr] {text}")

            await asyncio.wait_for(
                asyncio.gather(read_stdout(), read_stderr()),
                timeout=300,
            )
            await proc.wait()

            response = " ".join(response_parts).strip()
            if not response and success:
                response = "(commande exécutée, aucune réponse textuelle)"

            logger.info(f"OpenCode terminé: success={success}, session={session_id}")
            return {
                "success": success,
                "response": response,
                "session_id": session_id,
            }

        except FileNotFoundError:
            logger.error("OpenCode CLI non trouvé. Installez-le via https://opencode.ai")
            return {"success": False, "response": "", "session_id": ""}
        except Exception as e:
            logger.error(f"Erreur OpenCode run: {e}")
            return {"success": False, "response": str(e), "session_id": ""}
    
    def register_callback(self, callback: Callable[[Dict], Awaitable[None]]):
        self._callbacks.append(callback)

    async def _notify(self, event: Dict):
        self._notification_history.append(event)
        if len(self._notification_history) > self._max_history:
            self._notification_history.pop(0)
        
        for cb in self._callbacks:
            try:
                await cb(event)
            except Exception as e:
                logger.error(f"Erreur dans callback OpenCode: {e}")
        
        # --- INTEGRATION WEBSOCKET ---
        # Diffuser les logs bruts vers le salon "logs"
        await ws_manager.broadcast_to_channel("logs", {
            "type": "opencode_log",
            "content": event.get("content", ""),
            "timestamp": datetime.now().isoformat()
        })

        # Diffuser les événements critiques vers le salon "actions"
        if event.get("type") in ["success", "error", "file_update"]:
            await ws_manager.broadcast_to_channel("actions", {
                "type": "opencode_action",
                "content": event,
                "timestamp": datetime.now().isoformat()
            })

    def get_recent_notifications(self, limit: int = 10) -> List[Dict]:
        return self._notification_history[-limit:]

    async def stop(self):
        """Arrête proprement OpenCode"""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except:
                self.process.kill()
            logger.info("OpenCode arrêté")

# Singleton
_opencode_manager: Optional[OpenCodeConnectorManager] = None

def get_opencode_manager() -> OpenCodeConnectorManager:
    global _opencode_manager
    if _opencode_manager is None:
        _opencode_manager = OpenCodeConnectorManager()
    return _opencode_manager
