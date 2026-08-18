import logging
import json
import re
import uuid
from typing import List, Dict, Any
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionToolParam,
)
from backend.domain.core.models import EditorState as EditorStateModel
from backend.domain.core.editor_service import EditorService
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.filesystem_service import FilesystemService
from backend.application.intelligence.intelligence_service import init_intelligence_service, get_intelligence_service
from backend.application.intelligence.task_planner import get_task_planner
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager
from backend.domain.settings import settings
from backend.domain.core.events import emit_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5  # bounded tool-calling loop (native + tag fallback)


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
        self._sessions: Dict[str, List[ChatCompletionMessageParam]] = {}
        self._active_streams: Dict[str, bool] = {}
        self._max_sessions = 100

        self._init_intelligence()
        self.llm_client: OpenAI | None = None
        self._init_llm_client()

    def _init_llm_client(self):
        import os
        try:
            base_url = settings.hermes_llm_base_url or (settings.lmstudio_url.rstrip("/") + "/v1")
            self.llm_client = OpenAI(
                base_url=base_url,
                api_key=os.environ.get("HERMES_LLM_API_KEY", "lm-studio"),
            )
            self.llm_model = settings.hermes_llm_model
        except Exception as e:
            logger.warning(f"Failed to init LLM client: {e}")
            self.llm_client = None

    def _init_intelligence(self):
        from backend.application.intelligence.task_planner import init_task_planner
        try:
            base_url = settings.hermes_llm_base_url or (settings.lmstudio_url.rstrip("/") + "/v1")
            planner = init_task_planner(
                model_name=settings.hermes_llm_model,
                base_url=base_url,
            )
            init_intelligence_service(planner, None, self.connector_manager)
            self.intelligence_service = get_intelligence_service()
            logger.info("Hermes intelligence initialized with real TaskPlanner")
        except Exception as e:
            logger.warning(f"Failed to init real intelligence: {e}, using fallback")
            init_intelligence_service(get_task_planner(), None, self.connector_manager)
            self.intelligence_service = get_intelligence_service()

    def _build_tools(self) -> List[ChatCompletionToolParam]:
        """Convert list_tools() to OpenAI-compatible ``tools`` parameter.

        Each tool's ``input_schema`` (JSON Schema) becomes the function
        ``parameters`` so the LLM can emit native ``tool_calls``.
        """
        tools: List[ChatCompletionToolParam] = []
        for t in self.list_tools():
            if t["name"] == "chat":
                continue
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get(
                            "input_schema",
                            {"type": "object", "properties": {}},
                        ),
                    },
                }
            )
        return tools

    async def _execute_tool_call(
        self, func_name: str, func_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool and emit EventBus events for frontend visibility."""
        logger.info("Hermes executing tool: %s(%s)", func_name, func_args)
        try:
            result = await self.call_tool(func_name, func_args)
            emit_tool(func_name, func_args, result.get("content", ""), success=True)
            return result
        except Exception as e:
            emit_tool(func_name, func_args, str(e), success=False)
            raise

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
            state = self.state_store.get_state()
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
            return await self._handle_chat(
                arguments.get("message", ""),
                arguments.get("session_id"),
            )

        return {"content": f"Erreur : Outil {tool_name} non trouve."}

    async def _handle_chat(
        self, message: str, session_id: str | None = None
    ) -> Dict[str, Any]:
        if not self.llm_client:
            return {"content": "LLM client not available (check LM Studio on port 1234)."}

        try:
            session_id, history = self._get_or_create_session(session_id)
            tool_names = [t["name"] for t in self.list_tools() if t["name"] != "chat"]
            system_prompt = _build_system_prompt(tool_names)
            tools = self._build_tools()

            messages: List[ChatCompletionMessageParam] = [
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": message},
            ]

            for _ in range(MAX_TOOL_ROUNDS):
                if self._active_streams.get(session_id):
                    return {"content": "Cancelled.", "session_id": session_id}

                resp = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048,
                    tools=tools,
                    tool_choice="auto",
                    timeout=settings.llm_timeout,
                )

                msg = resp.choices[0].message
                content_text = msg.content or ""

                # Native tool calling (OpenAI-compatible)
                if msg.tool_calls:
                    tool_calls: List[ChatCompletionMessageToolCallParam] = []
                    for tc in msg.tool_calls:
                        fn = getattr(tc, "function", None)
                        if fn is None:
                            continue
                        tool_calls.append(
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": fn.name,
                                    "arguments": fn.arguments,
                                },
                            }
                        )
                    if tool_calls:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": content_text or None,
                                "tool_calls": tool_calls,
                            }
                        )
                        for tc in tool_calls:
                            func_name = tc["function"]["name"]
                            try:
                                func_args = json.loads(tc["function"]["arguments"] or "{}")
                            except json.JSONDecodeError:
                                func_args = {}
                            result = await self._execute_tool_call(func_name, func_args)
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": result.get("content", str(result)),
                                }
                            )
                    continue  # next round

                # Fallback: textual tag protocol (models without native tools)
                tool_call_match = parse_tool_call_tag(content_text)
                if tool_call_match:
                    func_name, func_args = tool_call_match
                    result = await self._execute_tool_call(func_name, func_args)
                    messages.extend(
                        build_followup_messages(content_text, func_name, func_args, result)
                    )
                    continue  # next round

                messages.append({"role": "assistant", "content": content_text})
                history[:] = messages[1:]
                return {"content": content_text, "session_id": session_id}

            history[:] = messages[1:]
            return {"content": "Tool call loop exceeded max rounds.", "session_id": session_id}

        except Exception as e:
            logger.exception("Chat LLM call failed")
            return {"content": f"Erreur LLM : {e}"}

    async def stream_chat(self, message: str, session_id: str | None = None):
        """Stream chat response token-by-token via async generator.

        Uses the same system prompt and tool-calling logic as _handle_chat
        but yields tokens as they arrive from the LLM for real-time display.
        Maintains per-session history and supports cancellation via cancel().
        """
        if not self.llm_client:
            yield "LLM client not available (check LM Studio on port 1234)."
            return

        try:
            session_id, history = self._get_or_create_session(session_id)
            self._active_streams[session_id] = self._active_streams.get(session_id, False)

            tool_names = [t["name"] for t in self.list_tools() if t["name"] != "chat"]
            system_prompt = _build_system_prompt(tool_names)
            tools = self._build_tools()

            messages: List[ChatCompletionMessageParam] = [
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": message},
            ]

            for _ in range(MAX_TOOL_ROUNDS):
                if self._active_streams.get(session_id):
                    yield "\n\n[cancelled]\n\n"
                    return

                stream = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048,
                    tools=tools,
                    tool_choice="auto",
                    stream=True,
                    timeout=settings.llm_timeout,
                )

                collected_content = ""
                tool_calls: Dict[int, Dict[str, str]] = {}
                for chunk in stream:
                    if self._active_streams.get(session_id):
                        yield "\n\n[cancelled]\n\n"
                        return
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta is None:
                        continue
                    if delta.content:
                        collected_content += delta.content
                        yield delta.content
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            entry = tool_calls.setdefault(
                                tc.index, {"id": "", "name": "", "arguments": ""}
                            )
                            if tc.id:
                                entry["id"] = tc.id
                            if tc.function and tc.function.name:
                                entry["name"] = tc.function.name
                            if tc.function and tc.function.arguments:
                                entry["arguments"] += tc.function.arguments

                # Native tool calls accumulated during streaming
                if tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": collected_content or None,
                            "tool_calls": [
                                {
                                    "id": entry["id"],
                                    "type": "function",
                                    "function": {
                                        "name": entry["name"],
                                        "arguments": entry["arguments"],
                                    },
                                }
                                for entry in tool_calls.values()
                            ],
                        }
                    )
                    for entry in tool_calls.values():
                        yield "\n\n[tool: {}\n\n".format(entry["name"])
                        try:
                            func_args = json.loads(entry["arguments"] or "{}")
                        except json.JSONDecodeError:
                            func_args = {}
                        result = await self._execute_tool_call(entry["name"], func_args)
                        yield "\n```json\n{}\n```\n\n".format(
                            json.dumps(result.get("content", ""), ensure_ascii=False)
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": entry["id"],
                                "content": result.get("content", str(result)),
                            }
                        )
                    continue  # next round

                # Fallback: textual tag protocol
                tool_call_match = parse_tool_call_tag(collected_content)
                if tool_call_match:
                    func_name, func_args = tool_call_match
                    yield "\n\n[tool: {}\n\n".format(func_name)
                    result = await self._execute_tool_call(func_name, func_args)
                    yield "\n```json\n{}\n```\n\n".format(
                        json.dumps(result.get("content", ""), ensure_ascii=False)
                    )
                    messages.extend(
                        build_followup_messages(collected_content, func_name, func_args, result)
                    )
                    continue  # next round

                messages.append({"role": "assistant", "content": collected_content})
                history[:] = messages[1:]
                return

            history[:] = messages[1:]
            yield "\n\nTool call loop exceeded max rounds."

        except Exception as e:
            logger.exception("Chat stream failed")
            yield f"Error: {e}"
        finally:
            if session_id:
                self._active_streams.pop(session_id, None)

    def _get_or_create_session(
        self, session_id: str | None
    ) -> tuple[str, List[ChatCompletionMessageParam]]:
        """Return (session_id, messages) for a conversation, creating it if needed.

        When no session_id is given a new one is generated. When the session
        store is at capacity the oldest session is evicted (dict preserves
        insertion order).
        """
        if session_id and session_id in self._sessions:
            return session_id, self._sessions[session_id]
        session_id = session_id or uuid.uuid4().hex[:12]
        if len(self._sessions) >= self._max_sessions:
            self._sessions.pop(next(iter(self._sessions)))
        self._sessions[session_id] = []
        return session_id, self._sessions[session_id]

    def cancel(self, session_id: str) -> bool:
        """Request cancellation of an active stream for a session.

        The streaming loop checks the flag between chunks and tool rounds.
        Returns True if a stream was active for this session.
        """
        if session_id in self._active_streams:
            self._active_streams[session_id] = True
            return True
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List active sessions with their message counts."""
        return [
            {"session_id": sid, "message_count": len(msgs)}
            for sid, msgs in self._sessions.items()
        ]

    def clear_session(self, session_id: str) -> bool:
        """Remove a session's history. Returns True if it existed."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._active_streams.pop(session_id, None)
            return True
        return False


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
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                # Models sometimes emit escaped quotes around keys
                # (e.g. {\"intent\": \"...\"}) -> normalize them.
                parsed = {
                    str(k).strip('\"\''): (
                        v.strip('\"\'') if isinstance(v, str) else v
                    )
                    for k, v in parsed.items()
                }
            return func_name, parsed
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


def build_followup_messages(original_text, func_name, func_args, result) -> List[ChatCompletionMessageParam]:
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


def get_server_state() -> dict[str, Any]:
    """Report the Hermes MCP server state without constructing it.

    The server is lazily created on the first get_server() call, so a
    fresh boot with no Hermes traffic has no instance yet. This accessor
    lets /health/deep (ADR D4) report whether the agent is present and its
    LLM client is initialized — without forcing construction.
    """
    if _server_instance is None:
        return {
            "initialized": False,
            "llm_client_ready": False,
            "intelligence_ready": False,
            "llm_model": None,
            "base_url": None,
        }
    server = _server_instance
    llm_client = server.llm_client
    return {
        "initialized": True,
        "llm_client_ready": llm_client is not None,
        "intelligence_ready": getattr(server, "intelligence_service", None) is not None,
        "llm_model": getattr(server, "llm_model", None),
        "base_url": getattr(llm_client, "base_url", None) if llm_client else None,
    }


__all__ = ["HermesMCPServer", "get_server", "get_server_state"]
