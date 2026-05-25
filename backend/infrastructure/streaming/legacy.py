"""
Legacy API: stream_chat() and create_sse_response().
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from backend.infrastructure.streaming.models import StreamChunk, StreamStatus
from backend.infrastructure.streaming.streamer import UnifiedStreamer
from backend.infrastructure.streaming.transports import SSETransport

logger = logging.getLogger(__name__)

_unified_streamer: UnifiedStreamer | None = None


def get_unified_streamer() -> UnifiedStreamer:
    global _unified_streamer
    if _unified_streamer is None:
        _unified_streamer = UnifiedStreamer()
    return _unified_streamer


async def create_sse_response(
    message: str,
    model: str,
    provider: str,
    temperature: float,
    session_id: str | None = None,
    resume_from: str | None = None,
    max_buffer: int = 64,
) -> StreamingResponse:
    """Create SSE StreamingResponse using unified streamer."""
    session_id = session_id or str(uuid.uuid4())[:8]
    streamer = get_unified_streamer()
    transport = SSETransport(max_buffer=max_buffer)

    async def sse_generator():
        async for event in streamer.stream(
            transport=transport,
            message=message,
            session_id=session_id,
            model=model,
            provider=provider,
            temperature=temperature,
            resume_from=resume_from,
        ):
            yield event.to_sse()

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def stream_chat(
    prompt: str,
    model: str = "",
    provider: str = "ollama",
    timeout: int | None = None,
) -> AsyncIterator[StreamChunk]:
    """Legacy API compatibility method — now backed by UnifiedStreamer.

    Deprecated: Use UnifiedStreamer.stream() directly for new code.
    """
    streamer = get_unified_streamer()
    transport = SSETransport()
    session_id = str(uuid.uuid4())[:8]
    index = 0
    token_count = 0

    try:
        async for event in streamer.stream(
            transport=transport,
            message=prompt,
            session_id=session_id,
            model=model,
            provider=provider,
        ):
            if event.event_type == "token":
                token_count += 1
                yield StreamChunk(
                    text=event.content,
                    status=StreamStatus.GENERATING,
                    stream_id=event.stream_id or "legacy",
                    chunk_index=index,
                    tokens_generated=token_count,
                )
                index += 1
            elif event.event_type == "done":
                yield StreamChunk(
                    text="",
                    status=StreamStatus.COMPLETED,
                    stream_id=event.stream_id or "legacy",
                    chunk_index=index,
                    tokens_generated=token_count,
                )
            elif event.event_type == "error":
                yield StreamChunk(
                    text=event.content,
                    status=StreamStatus.ERROR,
                    stream_id=event.stream_id or "legacy",
                    chunk_index=index,
                    error=event.error,
                )
    except asyncio.CancelledError:
        yield StreamChunk(
            text="",
            status=StreamStatus.CANCELLED,
            stream_id="legacy",
            chunk_index=index,
            error="Stream cancelled",
        )


__all__ = [
    "UnifiedStreamer",
    "create_sse_response",
    "get_unified_streamer",
    "stream_chat",
]
