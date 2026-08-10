import logging
import json
import re
from typing import List, Dict, Any, Optional
from openai import OpenAI
from backend.domain.core.models import EditorState as EditorStateModel
from backend.domain.core.editor_service import EditorService
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.filesystem_service import FilesystemService
from backend.application.intelligence.intelligence_service import init_intelligence_service, get_intelligence_service
from backend.application.intelligence.task_planner import get_task_planner
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

logger = logging.getLogger(__name__)


# ─── Shared Prompts ───────────────────────────────────

_SYSTEM_PROMPT_BASE = (
    "You are Hermes, the intelligence engine of UI-Pro. "
    "You run locally and CAN execute tasks on this machine. "
)

_SYSTEM_PROMPT_SUFFIX = (
    "When the user asks you to do something, use a tool. "
    "To call a tool, write on its own line:\n"
    "<|tool_call>call:TOOL_NAME{\"arg1\": \"value1\"}<tool_call|>\n"
    "Example: <|tool_call>call:execute_intent{\"intent\": \"launch msedge.exe\"}<tool_call|>\n"
    "If the command is simple (like launching an app), use execute_intent. "
    "Answer clearly and concisely in the language the user speaks."
)


def _build_system_prompt(tool_names: List[str]) -> str:
    """Build the system prompt with the list of available tools."""
    return (
        _SYSTEM_PROMPT_BASE
        + f"Available tools: {', '.join(tool_names)}. "
        + _SYSTEM_PROMPT_SUFFIX
    )
class HermesMCPServer:
    """
    Serveur MCP (Model Context Protocol) pour Hermes.
    Expose les capacites de planification, d'execution et de gestion de fichiers
    sous forme d'outils et de ressources standardises.
    """
    def __init__(self):
        self.filesystem_service = FilesystemService()
        self.state_store = EditorStateStore()
        self.editor_service = EditorService(self.state_store, self.filesystem_service)
        self.connector_manager = OpenCodeConnectorManager()

        self._init_intelligence()
        self.llm_client: OpenAI | None = None
        self._init_llm_client()

    def _init_llm_client(self):
        import os
        try:
            self.llm_client = OpenAI(
                base_url=os.environ.get("HERMES_LLM_BASE_URL", "http://localhost:1234/v1"),
                api_key=os.environ.get("HERMES_LLM_API_KEY", "lm-studio"),
            )
            self.llm_model = os.environ.get("HERMES_LLM_MODEL", "google/gemma-4-12b-qat")
        except Exception as e:
            logger.warning(f"Failed to init LLM client: {e}")
            self.llm_client = None

    def _init_intelligence(self):
        import asyncio
        from backend.application.intelligence.task_planner import init_task_planner
        try:
            planner = asyncio.run(init_task_planner(
                model_name="google/gemma-4-12b-qat",
                base_url="http://localhost:1234/v1",
            ))
            init_intelligence_service(planner, None, self.connector_manager)
            self.intelligence_service = get_intelligence_service()
            logger.info("Hermes intelligence initialized with real TaskPlanner")
        except Exception as e:
            logger.warning(f"Failed to init real intelligence: {e}, using fallback")
            init_intelligence_service(get_task_planner(), None, self.connector_manager)
            self.intelligence_service = get_intelligence_service()

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "execute_intent",
                "description": "Analyse une intention utilisateur et execute une serie d'actions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string", "description": "L'intention de l'utilisateur."},
                        "context": {"type": "string", "description": "Contexte additionnel (optionnel)."}
                    },
                    "required": ["intent"]
                }
            },
            {
                "name": "get_opencode_status",
                "description": "Recupere le statut et les dernieres actions d'OpenCode.",
                "input_schema": {"type": "object", "properties": {}}
            },
            {
                "name": "read_file",
                "description": "Lit le contenu d'un fichier specifique.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Chemin relatif du fichier."}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Ecrit ou cree un fichier.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Chemin relatif du fichier."},
                        "content": {"type": "string", "description": "Contenu a ecrire."}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "chat",
                "description": "Dialogue direct avec Hermes via LLM (chat libre).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message utilisateur."}
                    },
                    "required": ["message"]
                }
            }
        ]

    def list_resources(self) -> List[Dict[str, Any]]:
        return [
            {
                "uri": "hermes://editor_state",
                "name": "Editor State",
                "description": "L'etat actuel de l'editeur."
            },
            {
                "uri": "hermes://project_context",
                "name": "Project Context",
                "description": "Vue d'ensemble des fichiers et structure du projet."
            }
        ]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "execute_intent":
            stored = self.state_store.get_state()
            state = EditorStateModel(
                cursor=stored.cursor,
                selection=stored.selection,
                active_file=stored.active_file,
                diagnostics=stored.diagnostics,
                terminal_output=stored.terminal_output,
                git_status=stored.git_status,
            )
            actions = await self.intelligence_service.process_user_intent(
                arguments.get("intent", ""), state
            )
            return {"content": f"Actions generees : {actions}"}

        elif tool_name == "get_opencode_status":
            status = await self.intelligence_service.get_opencode_status()
            return {"content": status}

        elif tool_name == "read_file":
            path = arguments.get("path", "")
            file_data = self.filesystem_service.read_file(path)
            if file_data:
                return {"content": file_data.content}
            return {"content": f"Erreur : Fichier {path} non trouve."}

        elif tool_name == "write_file":
            path = arguments.get("path", "")
            content = arguments.get("content", "")
            success = self.filesystem_service.write_file(path, content)
            return {"content": "Succes" if success else "Echec de l'ecriture."}

        elif tool_name == "chat":
            return await self._handle_chat(arguments.get("message", ""))

        return {"content": f"Erreur : Outil {tool_name} non trouve."}

    async def _handle_chat(self, message: str) -> Dict[str, Any]:
        if not self.llm_client:
            return {"content": "LLM client not available (check LM Studio on port 1234)."}

        try:
            tool_names = [t["name"] for t in self.list_tools() if t["name"] != "chat"]

            system_prompt = _build_system_prompt(tool_names)

            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ]

            resp = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
            )

            content_text = resp.choices[0].message.content or ""

            tool_call_match = parse_tool_call_tag(content_text)
            if tool_call_match:
                func_name, func_args = tool_call_match
                logger.info(f"Hermes executing tool: {func_name}({func_args})")
                result = await self.call_tool(func_name, func_args)
                followup = build_followup_messages(content_text, func_name, func_args, result)
                messages.extend(followup)
                resp2 = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024,
                )
                return {"content": resp2.choices[0].message.content or "..."}

            return {"content": content_text}

        except Exception as e:
            logger.exception("Chat LLM call failed")
            return {"content": f"Erreur LLM : {e}"}

    async def stream_chat(self, message: str):
        """Stream chat response token-by-token via async generator.

        Uses the same system prompt and tool-calling logic as _handle_chat
        but yields tokens as they arrive from the LLM for real-time display.
        """
        if not self.llm_client:
            yield "LLM client not available (check LM Studio on port 1234)."
            return

        try:
            tool_names = [t["name"] for t in self.list_tools() if t["name"] != "chat"]

            system_prompt = _build_system_prompt(tool_names)

            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ]

            stream = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                stream=True,
            )

            collected_content = ""
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    collected_content += content
                    yield content

            # Handle tool calls (same logic as _handle_chat)
            tool_call_match = parse_tool_call_tag(collected_content)
            if tool_call_match:
                func_name, func_args = tool_call_match
                logger.info(f"Hermes executing tool: {func_name}({func_args})")
                yield "\n\n[tool: {}\n\n".format(func_name)
                result = await self.call_tool(func_name, func_args)
                yield "\n```json\n{}\n```\n\n".format(json.dumps(result.get("content", ""), ensure_ascii=False))
                followup = build_followup_messages(collected_content, func_name, func_args, result)
                messages.extend(followup)
                stream2 = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024,
                    stream=True,
                )

                for chunk in stream2:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield content

        except Exception as e:
            logger.exception("Chat stream failed")
            yield f"Error: {e}"


def parse_tool_call_tag(text: str):
    """
    Extract tool call from LLM response text.
    Supports:
      <|tool_call>call:NAME{json_args}<tool_call|>       (curly braces, JSON-ish)
      <|tool_call>call:NAME(key1="val1")<tool_call|>     (parens, key=value)
    """
    # Try {json_args} first
    m = re.search(
        r"<\|tool_call>call:(\w+)\{(.+?)\}<tool_call\|>",
        text, re.DOTALL
    )
    if m:
        func_name = m.group(1)
        raw = "{" + m.group(2) + "}"
        # Try real JSON parse (with quoted keys)
        try:
            return func_name, json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Fallback: key: value or "key": "value"
        return func_name, _parse_kv(m.group(2), ":")

    # Try (key=value) format
    m = re.search(
        r"<\|tool_call>call:(\w+)\(([^)]+)\)<tool_call\|>",
        text, re.DOTALL
    )
    if m:
        return m.group(1), _parse_kv(m.group(2), "=")

    return None


def _parse_kv(raw: str, sep: str = ":") -> dict:
    """Parse 'key1: val1, key2: \"val2\"' into dict."""
    result = {}
    for pair in raw.split(","):
        if sep in pair:
            k, v = pair.split(sep, 1)
            result[k.strip().strip('"\'')] = v.strip().strip('"\'')
    return result


def build_followup_messages(original_text, func_name, func_args, result):
    result_content = result.get("content", str(result)) if isinstance(result, dict) else str(result)
    return [{
        "role": "system",
        "content": (
            f"You called tool {func_name} with args {func_args}. "
            f"Result: {result_content}. "
            "Now summarize what was done for the user in a concise way. "
            "Respond in the same language the user used."
        )
    }]

_server_instance: HermesMCPServer | None = None


def get_server() -> HermesMCPServer:
    """Lazy-initialized singleton for HermesMCPServer.

    Avoids constructing the server (and its LLM client / intelligence service)
    at import time. Callers should use this instead of importing a module-level
    instance, so the server is only created when actually needed.
    """
    global _server_instance
    if _server_instance is None:
        _server_instance = HermesMCPServer()
    return _server_instance


__all__ = ["HermesMCPServer", "get_server"]
