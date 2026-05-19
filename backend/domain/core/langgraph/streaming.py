"""
Token streaming pipeline for the agent with batching and robust resume.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from .state import AgentState

logger = logging.getLogger(__name__)

# Batching: tokens per message (good compromise)
BATCH_SIZE = 6

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
    resume_from: Optional[str] = None,
):
    """
    Streaming optimisé avec batching et resume.

    Utilise astream_events pour des événements plus granulaires.
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

    try:
        yield "[STEP]orchestrator:Starting agent pipeline"

        # Use astream_events for more granular event handling
        async for event in app.astream_events(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
        ):
            event_type = event.get("event")

            # Gestion des steps (on_chain_start)
            if event_type == "on_chain_start":
                name = event.get("name", "unknown")
                yield f"[STEP]{name}:Starting"

            # Token streaming avec batching (on_chat_model_stream)
            if event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk", {})
                content = getattr(chunk, "content", None)

                if content:
                    token_buffer.append(content)
                    token_count += len(content)

                    # Envoyer quand le buffer atteint BATCH_SIZE
                    if len(token_buffer) >= BATCH_SIZE:
                        batch = "".join(token_buffer)
                        yield f"[TOKEN]{batch}"
                        token_buffer.clear()

                        # Sauvegarder checkpoint périodiquement
                        if token_count % 50 == 0:
                            save_stream_checkpoint(stream_id, session_id, token_count, {})

            # Événements terminaux (on_chain_end)
            if event_type == "on_chain_end":
                # Flush remaining tokens
                if token_buffer:
                    yield f"[TOKEN]{''.join(token_buffer)}"
                    token_buffer.clear()

                yield "[DONE]"

        # Save final checkpoint
        save_stream_checkpoint(stream_id, session_id, token_count, {})
        yield "[STEP]completed:Task completed successfully"

    except Exception as e:
        logger.exception("Streaming failed")
        # Save error checkpoint for potential resume
        save_stream_checkpoint(stream_id, session_id, token_count, {"error": str(e)})
        yield f"[ERROR]500:{str(e)}"
        yield "[DONE]"


__all__ = ["stream_agent", "get_stream_checkpoint", "save_stream_checkpoint"]