"""
Token streaming pipeline for the agent with batching and robust resume.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from backend.domain.core.events import EventType, get_event_bus

from .state import AgentState

logger = logging.getLogger(__name__)

# Batching: tokens per message (good compromise)
BATCH_SIZE = 6

_stream_checkpoints: dict[str, dict] = {}  # stream_id -> checkpoint data
_last_message_length: dict[str, int] = {}
# Track the index of the last assistant message we streamed tokens for,
# so we can detect when a NEW message is appended (e.g. the final summary
# in executing_node) vs when the same message is being extended in place.
# Without this, a short new message after a long plan would be silently
# dropped because the length-tracker only emits `len(content) > last_len`.
_last_msg_idx: dict[str, int] = {}


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


def get_stream_checkpoint(stream_id: str) -> dict | None:
    """Get checkpoint data for resuming a stream."""
    return _stream_checkpoints.get(stream_id)


def save_stream_checkpoint(
    stream_id: str, session_id: str, last_token_index: int, state: dict
):
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
    resume_from: str | None = None,
):
    """
    Streaming optimisé avec batching et resume.
    """
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

    _emit_step("orchestrator", f"Starting streaming session {session_id}")

    token_count = start_index
    token_buffer = []
    _last_message_length[session_id] = start_index

    try:
        yield "[STEP]orchestrator:Starting agent pipeline"
        logger.info("[streaming] Starting astream...")

        # Subscribe to event bus for step events emitted by nodes.py (_emit_step)
        # and generation stats emitted by LLMWrapper
        step_queue: asyncio.Queue[str] = asyncio.Queue()

        def _on_agent_event(event: Any) -> None:
            try:
                if hasattr(event, "step") and hasattr(event, "message"):
                    step_queue.put_nowait(f"{event.step}:{event.message}")
            except Exception:
                pass

        bus = get_event_bus()
        bus.subscribe(EventType.AGENT, _on_agent_event)

        # Track state fields already emitted (each only ONCE, not every snapshot)
        _state_emitted: set[str] = set()

        async for event in app.astream(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
            stream_mode="values",
        ):
            # Drain detailed sub-step events from nodes.py
            # (emitted during node execution via _emit_step → event bus)
            _step_dedup = set()
            try:
                while True:
                    step_msg = step_queue.get_nowait()
                    if step_msg not in _step_dedup:
                        _step_dedup.add(step_msg)
                        yield f"[STEP]{step_msg}"
            except asyncio.QueueEmpty:
                pass

            # State-based steps: emit each field ONLY ONCE (first time it appears)
            analyzing_val = event.get("task_type")
            if analyzing_val and "task_type" not in _state_emitted:
                _state_emitted.add("task_type")
                yield f"[STEP]analyzing:Classification: {analyzing_val[:80]}"

            plan_val = event.get("plan")
            if plan_val and "plan" not in _state_emitted:
                _state_emitted.add("plan")
                steps_count = len(plan_val.get("steps", []))
                yield f"[STEP]planning:Plan created ({steps_count} étapes)"

            code_val = event.get("code")
            if code_val and "code" not in _state_emitted:
                _state_emitted.add("code")
                files = code_val.get("files", {})
                yield f"[STEP]coding:Code generation completed ({len(files)} fichiers)"
                for filename, source in files.items():
                    yield f"[TOKEN]\n\n**{filename}**\n```python\n{source}\n```\n\n"

            review_val = event.get("review")
            if review_val and "review" not in _state_emitted:
                _state_emitted.add("review")
                status = "PASSED" if review_val.get("passed") else "Needs improvement"
                yield f"[STEP]reviewing:Review - {status}"

            exec_val = event.get("execution_result")
            if exec_val and "execution_result" not in _state_emitted:
                _state_emitted.add("execution_result")
                success = (
                    exec_val.get("success", False)
                    if isinstance(exec_val, dict)
                    else False
                )
                yield f"[STEP]executing:Execution {'OK' if success else 'FAILED'}"

            # Token streaming from latest assistant message
            if event.get("messages"):
                last_msg = event["messages"][-1]
                if last_msg.get("role") == "assistant":
                    content = last_msg.get("content", "")
                    # Detect a brand-new assistant message vs an in-place
                    # extension of the previous one. The summary appended
                    # by executing_node is a NEW message and would be
                    # missed by length-only tracking if it's shorter than
                    # the previous plan.
                    current_idx = len(event["messages"]) - 1
                    if _last_msg_idx.get(session_id) != current_idx:
                        last_len = 0
                        _last_msg_idx[session_id] = current_idx
                    else:
                        last_len = _last_message_length.get(
                            session_id, start_index
                        )

                    # Skip tokens already sent (for resume)
                    if start_index > 0 and len(content) > start_index:
                        content = content[start_index:]
                        last_len = start_index

                    if len(content) > last_len:
                        new_text = content[last_len:]
                        if new_text.strip():
                            logger.info(
                                f"[streaming] Token received: {new_text[:50]}..."
                            )
                            # Add to buffer for batching
                            token_buffer.append(new_text)
                            token_count += len(new_text)

                            # Send batch when buffer reaches BATCH_SIZE
                            if len(token_buffer) >= BATCH_SIZE:
                                batch = "".join(token_buffer)
                                yield f"[TOKEN]{batch}"
                                token_buffer.clear()

                                # Save checkpoint periodically
                                if token_count % 50 == 0:
                                    save_stream_checkpoint(
                                        stream_id, session_id, token_count, dict(event)
                                    )

                        _last_message_length[session_id] = len(content)

            # Tool events
            exec_result = event.get("execution_result")
            if exec_result and isinstance(exec_result, dict):
                if exec_result.get("files_written"):
                    for f in exec_result["files_written"]:
                        yield f"[TOOL]write_file:Created {f}"

        # Flush remaining tokens
        if token_buffer:
            yield f"[TOKEN]{''.join(token_buffer)}"

        # Save final checkpoint
        save_stream_checkpoint(stream_id, session_id, token_count, {})

        yield "[STEP]completed:Task completed successfully"
        yield "[DONE]"

    except Exception as e:
        logger.exception("Streaming failed")
        save_stream_checkpoint(stream_id, session_id, token_count, {"error": str(e)})
        yield f"[ERROR]500:{e!s}"
        yield "[DONE]"

    finally:
        _last_message_length.pop(session_id, None)
        _last_msg_idx.pop(session_id, None)
        try:
            bus.unsubscribe(EventType.AGENT, _on_agent_event)
        except Exception:
            pass


__all__ = ["get_stream_checkpoint", "save_stream_checkpoint", "stream_agent"]
