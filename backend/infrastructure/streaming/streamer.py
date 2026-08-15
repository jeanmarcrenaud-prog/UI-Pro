"""
UnifiedStreamer — main streaming orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import Request, WebSocket

from backend.infrastructure.streaming.models import StreamEvent, _TokenBuffer
from backend.infrastructure.streaming.parser import parse_event
from backend.infrastructure.streaming.transports import (
    SSETransport,
    StreamTransport,
    WebSocketTransport,
)

logger = logging.getLogger(__name__)

# Registry of active streams for server-side cancellation (SSE path).
# Maps stream_id -> {"cancelled": bool}
_active_streams: dict[str, dict[str, bool]] = {}


def cancel_stream(stream_id: str) -> bool:
    """Signal an in-flight stream to stop (used by the SSE cancel endpoint).

    The streaming loop checks the ``cancelled`` flag between chunks and
    breaks early.  This is a sync function so it can be called from a
    regular FastAPI endpoint without an event loop.

    Returns True if a stream was found and flagged for cancellation.
    """
    stream = _active_streams.get(stream_id)
    if stream is None:
        return False
    stream["cancelled"] = True
    return True


class UnifiedStreamer:
    """Unified streaming interface that handles both SSE and WebSocket.

    Usage:
        streamer = UnifiedStreamer()
        transport = streamer.detect_transport(request, websocket)
        async for event in streamer.stream(transport, prompt, model, provider):
            await transport.send(event)
    """

    def __init__(self):
        self._counter = 0
        self._lock = asyncio.Lock()

    def detect_transport(
        self,
        request: Request | None = None,
        websocket: WebSocket | None = None,
    ) -> StreamTransport:
        if websocket is not None:
            return WebSocketTransport(websocket)
        return SSETransport()

    async def stream(
        self,
        transport: StreamTransport,
        session_id: str,
        message: str = "",
        model: str = "",
        provider: str = "ollama",
        temperature: float = 0.7,
        max_attempts: int = 3,
        resume_from: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        async with self._lock:
            self._counter += 1
            stream_id = f"stream-{self._counter}-{uuid.uuid4().hex[:8]}"
        _active_streams[stream_id] = {"cancelled": False}

        message_id = str(uuid.uuid4())
        buf = _TokenBuffer()

        yield StreamEvent(
            event_type="stream_id",
            stream_id=stream_id,
            message_id=message_id,
        )

        if resume_from:
            yield StreamEvent(
                event_type="resumed",
                stream_id=resume_from,
                message_id=message_id,
            )

        try:
            from backend.domain.core.langgraph import stream_agent as langgraph_stream

            async for raw_event in langgraph_stream(
                message=message,
                session_id=session_id,
                model=model,
                provider=provider,
                max_attempts=max_attempts,
                resume_from=resume_from,
            ):
                if _active_streams.get(stream_id, {}).get("cancelled"):
                    break
                if not transport.is_connected:
                    break

                event = parse_event(raw_event, message_id)
                if not event:
                    continue

                if event.event_type == "token":
                    buf.append(event.content)
                    while buf.is_ready:
                        flush = buf.flush()
                        if flush:
                            yield flush
                else:
                    flush = buf.drain()
                    if flush:
                        yield flush
                    yield event

            flush = buf.drain()
            if flush:
                yield flush

            yield StreamEvent(event_type="done", message_id=message_id)

        except asyncio.CancelledError:
            yield StreamEvent(
                event_type="error",
                content="Stream cancelled by client",
                code="cancelled",
                message_id=message_id,
            )
            raise

        except Exception as e:
            logger.exception("Streaming error")
            yield StreamEvent(
                event_type="error",
                content=str(e),
                code="500",
                message_id=message_id,
            )
            yield StreamEvent(event_type="done", message_id=message_id)

        finally:
            _active_streams.pop(stream_id, None)


__all__ = ["UnifiedStreamer", "cancel_stream"]
