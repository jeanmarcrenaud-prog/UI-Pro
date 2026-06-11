"""
Token streaming pipeline for the agent with batching and robust resume.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from collections.abc import AsyncIterator
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
    from backend.infrastructure.monitoring.pipeline_metrics import inc_checkpoint_save

    inc_checkpoint_save()
    logger.info(f"[checkpoint] Saved for stream {stream_id}: {last_token_index} tokens")


# Map file extensions to language identifiers for markdown code fences.
# Used to replace the hardcoded "```python" when rendering generated code.
_EXT_TO_LANG: dict[str, str] = {
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".psd1": "powershell",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".bat": "batch",
    ".cmd": "batch",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
}


def _lang_for_file(filename: str, fallback_lang: str = "python") -> str:
    """Derive the language identifier for syntax highlighting from a filename."""
    ext = os.path.splitext(filename)[1].lower()
    return _EXT_TO_LANG.get(ext, fallback_lang)


async def stream_agent(
    message: str = "",
    session_id: str = "default",
    max_attempts: int = 3,
    model: str = "",
    provider: str = "ollama",
    resume_from: str | None = None,
    # Human-in-the-loop approval (Phase 2)
    decision: str | None = None,  # "execute" | "correct" | "cancel"
    feedback: str | None = None,  # User feedback for "correct"
):
    """
    Agent streaming with human-in-the-loop execution approval.

    Phase 1 (decision=None): analyze → plan → code → review, then interrupt
    BEFORE execute. Yields [AWAITING_APPROVAL] with the stream_id so the
    frontend can show "Execute / Correct / Cancel" buttons.

    Phase 2 (decision="execute"): resume from checkpoint → execute →
    should_continue → (fix_code loop | end). The fix loop auto-executes as
    before when execution fails, since the user already approved running.

    Phase 2 (decision="correct"): re-run code generation with user feedback
    as a new context message, then interrupt before execute again.

    Phase 2 (decision="cancel"): immediately end — code stays as-is.
    """
    from backend.domain.core.langgraph import get_orchestrator

    app = await get_orchestrator()

    # ── Phase 2: handle user decision ──────────────────────────
    if decision is not None:
        async for raw in _handle_decision(app, session_id, decision, feedback):
            yield raw
        return

    # ── Phase 1: code generation (analyze → plan → code → review) ──
    stream_id = str(uuid.uuid4())[:12]
    start_index = 0
    logger.info(f"[stream] Starting new stream {stream_id}")

    yield f"[STREAM_ID]{stream_id}"

    initial_state: AgentState = {
        "messages": [{"role": "user", "content": message}],
        "plan": None,
        "code": None,
        "review": None,
        "execution_result": None,
        "error": None,
        "awaiting_approval": False,
        "execution_decision": None,
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
        logger.info("[streaming] Starting astream (Phase 1 — interrupt before execute)...")

        step_queue: asyncio.Queue[str] = asyncio.Queue()

        def _on_agent_event(event: Any) -> None:
            try:
                if hasattr(event, "step") and hasattr(event, "message"):
                    step_queue.put_nowait(f"{event.step}:{event.message}")
            except Exception:
                pass

        bus = get_event_bus()
        bus.subscribe(EventType.AGENT, _on_agent_event)

        _state_emitted: set[str] = set()

        async for event in app.astream(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
            stream_mode="values",
            interrupt_before=["execute"],
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
                code_lang = event.get("language") or (_lang_for_file(list(files.keys())[0]) if files else "python")
                for filename, source in files.items():
                    file_lang = _lang_for_file(filename, code_lang)
                    yield f"[TOKEN]\n\n**{filename}**\n```{file_lang}\n{source}\n```\n\n"

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

        # If execution_result was NOT emitted, the graph was interrupted
        # before "execute" — yield AWAITING_APPROVAL instead of completed.
        if "execution_result" not in _state_emitted:
            logger.info(
                f"[stream] Phase 1 complete — yielding AWAITING_APPROVAL "
                f"(stream_id={stream_id})"
            )
            yield f"[AWAITING_APPROVAL]stream_id:{stream_id}"
        else:
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


# ── Phase 2 helpers ──────────────────────────────────────────────


async def _handle_decision(
    app: Any,
    session_id: str,
    decision: str,
    feedback: str | None,
) -> AsyncIterator[str]:
    """Handle Phase 2 user decision after the graph is interrupted."""

    if decision == "execute":
        async for raw in _resume_execution(app, session_id):
            yield raw
    elif decision == "correct":
        async for raw in _resume_correct(app, session_id, feedback):
            yield raw
    elif decision == "cancel":
        yield "[STEP]completed:Code generated (execution skipped by user)"
        yield "[DONE]"
    else:
        yield f"[ERROR]400:Unknown decision: {decision}"
        yield "[DONE]"


async def _resume_execution(app: Any, session_id: str) -> AsyncIterator[str]:
    """Phase 2 execute: resume from checkpoint → execute → should_continue → ...

    Uses a **dual-producer** pattern so that execution output (``[EXEC_OUT]``
    lines emitted by ``executing_node`` via the EventBus) can be interleaved
    with LangGraph state events in real-time:

      Producer 1 (background task): ``app.astream()`` → state events
      Producer 2 (EventBus subscriber): ``EXEC_OUTPUT`` → exec output lines
      Consumer (this coroutine): unified ``output_queue`` → WebSocket events
    """
    logger.info(f"[stream] Phase 2: resuming execution (session={session_id})")

    yield "[STEP]orchestrator:Executing code..."

    # ── Unified queue + producers ────────────────────────────────────
    bus = get_event_bus()
    output_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

    # Producer 1: LangGraph state events (runs in background)
    async def _astream_producer() -> None:
        try:
            async for event in app.astream(
                None,  # None = resume from last checkpoint
                config={"configurable": {"thread_id": session_id}},
                stream_mode="values",
            ):
                await output_queue.put(("state", event))
        except Exception as exc:
            logger.exception("[stream] astream producer failed")
            await output_queue.put(("error", str(exc)))
        finally:
            await output_queue.put(("__DONE__", None))

    astream_task = asyncio.create_task(_astream_producer())

    # Producer 2: execution output lines (from executing_node via EventBus)
    def _on_agent_event(event: Any) -> None:
        try:
            if hasattr(event, "step") and hasattr(event, "message"):
                output_queue.put_nowait(("step", f"{event.step}:{event.message}"))
        except Exception:
            pass

    def _on_exec_output(event: Any) -> None:
        try:
            line = getattr(event, "line", None) or getattr(event, "content", "")
            channel = getattr(event, "channel", "stdout")
            if line:
                output_queue.put_nowait(("exec_out", (line, channel)))
        except Exception:
            pass

    bus.subscribe(EventType.AGENT, _on_agent_event)
    bus.subscribe(EventType.EXEC_OUTPUT, _on_exec_output)

    # ── Consumer loop ────────────────────────────────────────────────
    _state_emitted: set[str] = set()
    token_buffer: list[str] = []
    _last_message_length[session_id] = 0

    try:
        while True:
            msg_type, payload = await output_queue.get()

            # ── Termination ──────────────────────────────────────────
            if msg_type == "__DONE__":
                break
            if msg_type == "error":
                yield f"[ERROR]500:{payload}"
                yield "[DONE]"
                return

            # ── Execution output line → terminal panel ───────────────
            if msg_type == "exec_out":
                line, _channel = payload
                yield f"[EXEC_OUT]{line}"
                continue

            # ── Agent step (from EventBus) ────────────────────────────
            if msg_type == "step":
                yield f"[STEP]{payload}"
                continue

            # ── LangGraph state event ─────────────────────────────────
            if msg_type == "state":
                event = payload

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
                        current_idx = len(event["messages"]) - 1
                        if _last_msg_idx.get(session_id) != current_idx:
                            last_len = 0
                            _last_msg_idx[session_id] = current_idx
                        else:
                            last_len = _last_message_length.get(session_id, 0)

                        if len(content) > last_len:
                            new_text = content[last_len:]
                            if new_text.strip():
                                token_buffer.append(new_text)
                                if len(token_buffer) >= BATCH_SIZE:
                                    batch = "".join(token_buffer)
                                    yield f"[TOKEN]{batch}"
                                    token_buffer.clear()
                            _last_message_length[session_id] = len(content)
                continue

    except Exception as e:
        logger.exception("[stream] Phase 2 execution failed")
        yield f"[ERROR]500:{e!s}"
    finally:
        if token_buffer:
            yield f"[TOKEN]{''.join(token_buffer)}"
        bus.unsubscribe(EventType.AGENT, _on_agent_event)
        bus.unsubscribe(EventType.EXEC_OUTPUT, _on_exec_output)
        _last_message_length.pop(session_id, None)
        _last_msg_idx.pop(session_id, None)

    yield "[STEP]completed:Execution completed"
    yield "[DONE]"


async def _resume_correct(
    app: Any,
    session_id: str,
    feedback: str | None,
) -> AsyncIterator[str]:
    """Phase 2 correct: re-run code gen with user feedback."""
    logger.info(
        f"[stream] Phase 2: correcting code (session={session_id}, "
        f"feedback={feedback})"
    )

    # Get the last checkpoint state to preserve plan/metadata
    try:
        state_snapshot = await app.aget_state(
            config={"configurable": {"thread_id": session_id}}
        )
    except Exception:
        state_snapshot = None

    base_state = dict(state_snapshot.values) if state_snapshot else {}

    feedback_msg = feedback or "Please correct the code."

    # TypedDict is too strict for dynamic state; pass raw dict
    modified_state: dict[str, Any] = {
        "messages": base_state.get("messages", [])
        + [{"role": "user", "content": feedback_msg}],
        "plan": base_state.get("plan"),  # keep plan for context
        "code": None,  # re-generate
        "review": None,  # re-review
        "execution_result": None,
        "error": None,
        "awaiting_approval": False,
        "execution_decision": None,
        "attempt": base_state.get("attempt", 0) + 1,
        "max_attempts": base_state.get("max_attempts", 3),
        "session_id": f"{session_id}_correct",
        "metadata": base_state.get("metadata"),
        "stream_id": base_state.get("stream_id"),
        "last_token_index": 0,
        "checkpoint_enabled": True,
    }

    yield "[STEP]orchestrator:Regenerating code with feedback..."

    _state_emitted: set[str] = set()
    token_buffer: list[str] = []

    try:
        async for event in app.astream(
            modified_state,
            config={"configurable": {"thread_id": f"{session_id}_correct"}},
            stream_mode="values",
            interrupt_before=["execute"],
        ):
            code_val = event.get("code")
            if code_val and "code" not in _state_emitted:
                _state_emitted.add("code")
                files = code_val.get("files", {})
                yield f"[STEP]coding:Code regenerated ({len(files)} fichiers)"
                code_lang = event.get("language") or (_lang_for_file(list(files.keys())[0]) if files else "python")
                for filename, source in files.items():
                    file_lang = _lang_for_file(filename, code_lang)
                    yield f"[TOKEN]\n\n**{filename}**\n```{file_lang}\n{source}\n```\n\n"

            review_val = event.get("review")
            if review_val and "review" not in _state_emitted:
                _state_emitted.add("review")
                status = "PASSED" if review_val.get("passed") else "Needs improvement"
                yield f"[STEP]reviewing:Review - {status}"

            # Token streaming
            if event.get("messages"):
                last_msg = event["messages"][-1]
                if last_msg.get("role") == "assistant":
                    content = last_msg.get("content", "")
                    current_idx = len(event["messages"]) - 1
                    if _last_msg_idx.get(f"{session_id}_correct") != current_idx:
                        last_len = 0
                        _last_msg_idx[f"{session_id}_correct"] = current_idx
                    else:
                        last_len = _last_message_length.get(f"{session_id}_correct", 0)
                    if len(content) > last_len:
                        new_text = content[last_len:]
                        if new_text.strip():
                            token_buffer.append(new_text)
                            if len(token_buffer) >= BATCH_SIZE:
                                yield f"[TOKEN]{''.join(token_buffer)}"
                                token_buffer.clear()
                        _last_message_length[f"{session_id}_correct"] = len(content)

    except Exception as e:
        logger.exception("[stream] Phase 2 correction failed")
        yield f"[ERROR]500:{e!s}"
    finally:
        if token_buffer:
            yield f"[TOKEN]{''.join(token_buffer)}"

    # After correction, yield AWAITING_APPROVAL again
    yield f"[AWAITING_APPROVAL]stream_id:{base_state.get('stream_id', 'unknown')}"
    yield "[DONE]"


__all__ = [
    "get_stream_checkpoint",
    "save_stream_checkpoint",
    "stream_agent",
]
