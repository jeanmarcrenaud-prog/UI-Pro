"""LangGraph bridge to Hermes ACP backend.

Exposes Hermes's agentic capabilities (file I/O, terminal execution,
intent processing, OpenCode status) as LangGraph-compatible tools that
the orchestrator pipeline can invoke from any node.

The bridge uses the ``HermesACPBackend`` (Phase 4) to communicate with
the ``hermes acp`` subprocess via the Agent Client Protocol (ACP) over
stdio.  Each tool call spawns a fresh Hermes session, sends the tool
request, and collects the response.

Usage::

    from backend.domain.core.langgraph.hermes_bridge import get_hermes_tools

    tools = get_hermes_tools()
    # tools is a list of dicts compatible with LangGraph's tool schema

    result = await call_hermes_tool("read_file", {"path": "main.py"})
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from backend.domain.core.events import emit_tool
from backend.domain.settings import settings

logger = logging.getLogger(__name__)

# ── Tool definitions ──────────────────────────────────────────────────────

HERMES_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "hermes_read_file",
        "description": (
            "Read the content of a file on the local filesystem. "
            "Returns the file content as a string, or an error message "
            "if the file cannot be read."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative to the workspace).",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "hermes_write_file",
        "description": (
            "Write or create a file on the local filesystem. "
            "If the file exists it will be overwritten."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write (relative to the workspace).",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "hermes_execute_intent",
        "description": (
            "Execute a user intent by delegating to the Hermes intelligence "
            "engine. Hermes will analyse the intent and perform the appropriate "
            "sequence of actions (file operations, app launches, etc.)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "The user intent to execute (e.g. 'open VS Code', 'read the config file').",
                },
                "context": {
                    "type": "string",
                    "description": "Optional additional context for the intent.",
                },
            },
            "required": ["intent"],
        },
    },
    {
        "name": "hermes_get_opencode_status",
        "description": (
            "Retrieve the current status and recent activity of the OpenCode "
            "connector (running sessions, recent actions, etc.)."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def get_hermes_tools() -> list[dict[str, Any]]:
    """Return the list of Hermes tool definitions for LangGraph.

    Each entry follows the LangGraph tool schema::

        {"name": str, "description": str, "parameters": {...}}

    These can be registered with a LangGraph agent via
    ``agent.bind_tools(get_hermes_tools())`` or used directly with
    :func:`call_hermes_tool`.
    """
    return [dict(t) for t in HERMES_TOOL_DEFINITIONS]


def get_hermes_tool_names() -> list[str]:
    """Return just the names of available Hermes tools."""
    return [t["name"] for t in HERMES_TOOL_DEFINITIONS]


# ── Tool invocation ───────────────────────────────────────────────────────


def _get_hermes_backend():
    """Get a HermesACPBackend instance (lazy import to avoid circular deps)."""
    from backend.infrastructure.llm.factory import get_backend

    return get_backend("hermes_acp")


def _build_hermes_prompt(tool_name: str, arguments: dict[str, Any]) -> str:
    """Build a prompt that instructs Hermes to call the requested tool.

    The Hermes agent understands the ``<|tool_call>call:NAME{json}<tool_call|>``
    protocol (see ``backend/infrastructure/mcp/server.py``).  We embed the
    tool name and JSON-serialised arguments into this protocol so Hermes
    executes the action and returns the result.
    """
    # Map our bridge tool names to the Hermes MCP server's internal tool names
    tool_map = {
        "hermes_read_file": "read_file",
        "hermes_write_file": "write_file",
        "hermes_execute_intent": "execute_intent",
        "hermes_get_opencode_status": "get_opencode_status",
    }
    internal_name = tool_map.get(tool_name, tool_name)

    args_json = json.dumps(arguments, ensure_ascii=False)
    return f"<|tool_call>call:{internal_name}{{{args_json}}}<tool_call|>"


async def call_hermes_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    cwd: str | None = None,
) -> str:
    """Invoke a Hermes tool via the ACP backend and return the result.

    Spawns a fresh ``hermes acp`` subprocess, sends the tool-call prompt,
    and collects the full response.  The result is also emitted on the
    EventBus so the frontend Debug panel can display tool activity.

    Args:
        tool_name: One of :func:`get_hermes_tool_names`.
        arguments: Keyword arguments for the tool (validated against the
            tool's parameter schema).
        cwd: Working directory for the Hermes subprocess (defaults to
            ``os.getcwd()``).

    Returns:
        The tool result as a string.

    Raises:
        ValueError: If *tool_name* is not a recognised Hermes tool.
        LLMConnectionError: If the Hermes subprocess cannot be reached.
    """
    if tool_name not in get_hermes_tool_names():
        raise ValueError(
            f"Unknown Hermes tool: {tool_name!r}. "
            f"Available: {get_hermes_tool_names()}"
        )

    backend = _get_hermes_backend()
    prompt = _build_hermes_prompt(tool_name, arguments)

    # Emit a tool event for frontend visibility
    emit_tool(tool_name, arguments, None, success=True)

    try:
        # HermesACPBackend.astream is an async generator — collect the full
        # response.  All registered LLMBackend subclasses implement astream.
        chunks: list[str] = []
        async for chunk in backend.astream(prompt, cwd=cwd):
            chunks.append(chunk)
        result = "".join(chunks)
    except asyncio.CancelledError:
        logger.warning("Hermes tool %s cancelled", tool_name)
        emit_tool(tool_name, arguments, "cancelled", success=False)
        raise
    except Exception as e:
        logger.error("Hermes tool %s failed: %s", tool_name, e)
        emit_tool(tool_name, arguments, str(e), success=False)
        raise

    emit_tool(tool_name, arguments, result, success=True)
    return result


# ── LangGraph node helpers ─────────────────────────────────────────────────


async def hermes_execute_node(
    state: dict[str, Any],
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Execute a Hermes tool from within a LangGraph node.

    This is a convenience wrapper that:
    1. Calls :func:`call_hermes_tool`.
    2. Emits a step event for the Agent Canvas.
    3. Returns a state update dict suitable for merging into ``AgentState``.

    Example::

        updates = await hermes_execute_node(state, "hermes_read_file", {"path": "main.py"})
        # merge the returned dict into the node's own state update
    """
    from backend.domain.core.langgraph.nodes._base import _emit_step

    _emit_step(
        "hermes", f"Calling {tool_name}...", data={"tool": tool_name, "args": arguments}
    )

    try:
        result = await call_hermes_tool(tool_name, arguments)
        _emit_step(
            "hermes", f"{tool_name} completed", data={"result_length": len(result)}
        )
        return {
            "hermes_tool_result": {
                "tool": tool_name,
                "arguments": arguments,
                "result": result,
                "success": True,
            }
        }
    except Exception as e:
        _emit_step("hermes", f"{tool_name} failed: {e}", data={"error": str(e)})
        return {
            "hermes_tool_result": {
                "tool": tool_name,
                "arguments": arguments,
                "result": str(e),
                "success": False,
            }
        }


def is_hermes_provider(provider: str) -> bool:
    """Check whether the given provider name routes through Hermes ACP."""
    return provider.lower() in ("hermes", "hermes_acp")


def should_use_hermes(state: dict[str, Any]) -> bool:
    """Determine whether the current pipeline state should delegate to Hermes.

    Returns True when the user has explicitly selected a Hermes provider
    in the chat metadata, or when the ``hermes_acp_provider`` setting is
    enabled for the current task type.
    """
    metadata = state.get("metadata") or {}
    provider = metadata.get("provider", "")
    if is_hermes_provider(provider):
        return True

    # Check per-task-type override in settings
    task_type = state.get("task_type", "")
    if task_type:
        try:
            task_json = (
                json.loads(task_type) if isinstance(task_type, str) else task_type
            )
            if isinstance(task_json, dict):
                task_type = task_json.get("task_type", "")
        except (json.JSONDecodeError, TypeError):
            pass

    # Allow hermes_acp_provider setting to force Hermes for specific task types
    hermes_tasks = getattr(settings, "hermes_acp_provider", "")
    if hermes_tasks and task_type in hermes_tasks.split(","):
        return True
    return False


__all__ = [
    "HERMES_TOOL_DEFINITIONS",
    "call_hermes_tool",
    "get_hermes_tool_names",
    "get_hermes_tools",
    "hermes_execute_node",
    "is_hermes_provider",
    "should_use_hermes",
]
