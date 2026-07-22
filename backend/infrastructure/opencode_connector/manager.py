from typing import Optional, Dict, Any, List
import json
import logging
import asyncio
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class OpenCodeResponse:
    type: str
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class OpenCodeClient:
    """
    Handles the low-level WebSocket communication with the OpenCode CLI/Server.
    """
    def __init__(self, ws_url: str, api_key: str, model_id: str):
        self.ws_url = ws_url
        self.api_key = api_key
        self.model_id = model_id
        self.ws = None
        self.is_running = False

    async def connect(self):
        import websockets
        try:
            self.ws = await websockets.connect(
                self.ws_url,
                extra_headers={"Authorization": f"Bearer {self.api_key}"}
            )
            self.is_running = True
            logger.info(f"Connected to OpenCode at {self.ws_url}")
        except Exception as e:
            logger.error(f"Failed to connect to OpenCode: {e}")
            self.is_running = False
            raise

    async def send_request(self, prompt: str) -> OpenCodeResponse:
        if not self.ws or not self.is_running:
            raise ConnectionError("OpenCode client is not connected.")

        payload = {
            "prompt": prompt,
            "model": self.model_id,
            "format": "json"
        }

        try:
            await self.ws.send(json.dumps(payload))
            response_raw = await self.ws.recv()
            data = json.loads(response_raw)
            return OpenCodeResponse(
                type=data.get("type", "text"),
                content=data.get("content"),
                metadata=data.get("metadata")
            )
        except Exception as e:
            logger.error(f"Error during OpenCode request: {e}")
            raise

    async def close(self):
        if self.ws:
            await self.ws.close()
            self.is_running = False

class OpenCodeConnectorManager:
    """
    Manages the lifecycle of the OpenCode connection and provides
    a high-level API for the IntelligenceService.
    """
    def __init__(self, ws_url: str = "", api_key: str = "", model_id: str = ""):
        self.ws_url = ws_url
        self.api_key = api_key
        self.model_id = model_id
        self.client: Optional[OpenCodeClient] = None
        self._lock = asyncio.Lock()

    async def get_client(self) -> OpenCodeClient:
        if self.client is None:
            # Check if URL is provided, else we might be in a fallback-ready state
            if not self.ws_url:
                logger.warning("OpenCode ws_url is missing. Connector will operate in fallback-ready state.")
            
            self.client = OpenCodeClient(self.ws_url, self.api_key, self.model_id)
            try:
                await self.client.connect()
            except Exception:
                # We don't raise here to allow the manager to exist even if connection fails
                logger.error("OpenCodeClient failed to connect. Manager is active but in fallback mode.")
        return self.client

    async def run_task(self, prompt: str) -> str:
        """
        Runs a task via OpenCode. Falls back to a 'local' message if connection is down.
        """
        try:
            client = await self.get_client()
            if not client.is_running:
                raise ConnectionError("OpenCode client is not running.")

            response = await client.send_request(prompt)
            
            if response.type == "step_finish":
                return f"SUCCESS: {response.content}"
            return response.content or ""

        except Exception as e:
            logger.error(f"OpenCode Connector Error: {e}")
            # Robust Fallback: Instead of crashing, we return a structured error message 
            # that the IntelligenceService can interpret as a failure to delegate.
            return f"ERROR: OpenCode unavailable. Reason: {str(e)}"

    def get_recent_notifications(self, limit: int = 10) -> List[Dict[str, str]]:
        return [
            {"type": "info", "content": "OpenCode connector status: Ready (check logs for connectivity)."}
        ]

    async def shutdown(self):
        if self.client:
            await self.client.close()
