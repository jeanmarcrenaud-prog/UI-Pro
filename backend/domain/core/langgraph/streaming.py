"""Token streaming pipeline for the agent."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from .state import AgentState

logger = logging.getLogger(__name__)

_last_message_length: dict[str, int] = {}


def _emit_step(phase: str, message: str):
    """Emit agent step event, stripping non-ASCII for Windows console."""
    try:
        try:
            message.encode("cp1252").decode("cp1252")
        except (UnicodeEncodeError, UnicodeDecodeError):
            message = message.encode("ascii", "replace").decode("ascii")
        from backend.domain.core.events import emit_agent_step
        emit_agent_step(phase, message)
    except Exception:
        pass


async def stream_agent(
    message: str,
    session_id: str = "default",
    max_attempts: int = 3,
    model: str = "",
    provider: str = "ollama",
):
    """Stream agent with step events and token emission."""
    from backend.domain.core.langgraph import build_graph
    app = build_graph()

    initial_state: AgentState = {
        "messages": [{"role": "user", "content": message}],
        "plan": None,
        "code": None,
        "review": None,
        "execution_result": None,
        "error": None,
        "attempt": 0,
        "max_attempts": max_attempts,
        "session_id": session_id,
        "metadata": {
            "start_time": datetime.now().isoformat(),
            "model": model,
            "provider": provider,
        },
    }

    _last_message_length[session_id] = 0
    _emit_step("orchestrator", f"Starting streaming session {session_id}")

    try:
        yield "[STEP]orchestrator:Starting agent pipeline"

        async for event in app.astream(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
            stream_mode="values",
        ):
            # Step events from full state snapshots
            plan_val = event.get("plan")
            if plan_val:
                yield "[STEP]planning:Plan created"

            code_val = event.get("code")
            if code_val:
                yield "[STEP]coding:Code generation completed"

            review_val = event.get("review")
            if review_val:
                status = "PASSED" if review_val.get("passed") else "Needs improvement"
                yield f"[STEP]reviewing:Review - {status}"

            exec_val = event.get("execution_result")
            if exec_val:
                success = exec_val.get("success", False) if isinstance(exec_val, dict) else False
                yield f"[STEP]executing:Execution {'OK' if success else 'FAILED'}"

            # Token streaming from latest assistant message
            if "messages" in event and event["messages"]:
                last_msg = event["messages"][-1]
                if last_msg.get("role") == "assistant":
                    content = last_msg.get("content", "")
                    last_len = _last_message_length.get(session_id, 0)
                    if len(content) > last_len:
                        new_text = content[last_len:]
                        if new_text.strip():
                            yield f"[TOKEN]{new_text}"
                        _last_message_length[session_id] = len(content)

            # Tool events
            exec_result = event.get("execution_result")
            if exec_result and isinstance(exec_result, dict):
                if exec_result.get("files_written"):
                    for f in exec_result["files_written"]:
                        yield f"[TOOL]write_file:Created {f}"

        yield "[STEP]completed:Task completed successfully"
        yield "[DONE]"

    except Exception as e:
        logger.exception("Streaming failed")
        yield f"[ERROR]500:{str(e)}"
        yield "[DONE]"

    finally:
        _last_message_length.pop(session_id, None)