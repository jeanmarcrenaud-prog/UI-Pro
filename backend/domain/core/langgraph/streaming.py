"""Token streaming pipeline for the agent."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from .state import AgentState

logger = logging.getLogger(__name__)

_last_message_length: dict[str, int] = {}
_stream_checkpoints: dict[str, dict] = {}  # stream_id -> checkpoint data


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


def get_stream_checkpoint(stream_id: str) -> Optional[dict]:
    """Get checkpoint data for resuming a stream."""
    return _stream_checkpoints.get(stream_id)


def save_stream_checkpoint(stream_id: str, session_id: str, last_token_index: int, state: dict):
    """Save checkpoint for potential resume."""
    _stream_checkpoints[stream_id] = {
        "session_id": session_id,
        "last_token_index": last_token_index,
        "state": state,
        "timestamp": datetime.now().isoformat(),
    }
    logger.info(f"[checkpoint] Saved for stream {stream_id}: {last_token_index} tokens")


async def stream_agent(
    message: str,
    session_id: str = "default",
    max_attempts: int = 3,
    model: str = "",
    provider: str = "ollama",
    resume_from: Optional[str] = None,  # stream_id to resume from
):
    """Stream agent with step events, token emission, and checkpoint support."""
    from backend.domain.core.langgraph import get_orchestrator
    app = await get_orchestrator()

    # Generate or resume stream_id
    if resume_from and resume_from in _stream_checkpoints:
        checkpoint = _stream_checkpoints[resume_from]
        stream_id = resume_from
        start_index = checkpoint["last_token_index"]
        logger.info(f"[stream] Resuming stream {stream_id} from index {start_index}")
        yield f"[RESUME]stream_id:{stream_id}:from_index:{start_index}"
    else:
        stream_id = str(uuid.uuid4())[:12]
        start_index = 0
        logger.info(f"[stream] Starting new stream {stream_id}")

    # Emit stream_id immediately
    yield f"[STREAM_ID]{stream_id}"

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
            "stream_id": stream_id,
        },
        "stream_id": stream_id,
        "last_token_index": start_index,
        "checkpoint_enabled": True,
    }

    _last_message_length[session_id] = start_index
    _emit_step("orchestrator", f"Starting streaming session {session_id}")

    token_count = start_index

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

            # Token streaming from latest assistant message (with resume support)
            if "messages" in event and event["messages"]:
                last_msg = event["messages"][-1]
                if last_msg.get("role") == "assistant":
                    content = last_msg.get("content", "")
                    last_len = _last_message_length.get(session_id, start_index)
                    
                    # Skip tokens already sent (for resume)
                    if start_index > 0 and len(content) > start_index:
                        content = content[start_index:]
                        last_len = start_index
                    
                    if len(content) > last_len:
                        new_text = content[last_len:]
                        if new_text.strip():
                            yield f"[TOKEN]{new_text}"
                            token_count += len(new_text)
                        
                        # Save checkpoint periodically (every 50 tokens)
                        if token_count % 50 == 0:
                            save_stream_checkpoint(stream_id, session_id, token_count, dict(event))
                        
                        _last_message_length[session_id] = len(content)

            # Tool events
            exec_result = event.get("execution_result")
            if exec_result and isinstance(exec_result, dict):
                if exec_result.get("files_written"):
                    for f in exec_result["files_written"]:
                        yield f"[TOOL]write_file:Created {f}"

        # Save final checkpoint
        save_stream_checkpoint(stream_id, session_id, token_count, {})
        
        yield "[STEP]completed:Task completed successfully"
        yield "[DONE]"

    except Exception as e:
        logger.exception("Streaming failed")
        # Save error checkpoint for potential resume
        save_stream_checkpoint(stream_id, session_id, token_count, {"error": str(e)})
        yield f"[ERROR]500:{str(e)}"
        yield "[DONE]"

    finally:
        _last_message_length.pop(session_id, None)


__all__ = ["stream_agent", "get_stream_checkpoint", "save_stream_checkpoint"]


__all__ = ["stream_agent", "get_stream_checkpoint", "save_stream_checkpoint"]