"""
backend/infrastructure/streaming_unified.py - Unified Streaming Protocol

Hybrid SSE + WebSocket streaming with auto-detection of client capability.
Provides a single interface that routes to SSE or WS based on transport.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from fastapi import Request, WebSocket
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


# ====================== Constants ======================

CHUNK_THRESHOLD = 20  # chars ~5 tokens before yielding a token event


# ====================== Types ======================


class StreamStatus(Enum):
    STARTING = "starting"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


# ====================== Token Buffer ======================


class _TokenBuffer:
    """Accumulates tokens and flushes in chunks or on demand."""

    def __init__(self, chunk_threshold: int = CHUNK_THRESHOLD):
        self._buffer = ""
        self._total = 0
        self._threshold = chunk_threshold

    def append(self, content: str) -> None:
        self._buffer += content
        self._total += len(content)

    @property
    def size(self) -> int:
        return len(self._buffer)

    @property
    def total(self) -> int:
        return self._total

    @property
    def is_ready(self) -> bool:
        return self.size >= self._threshold

    @property
    def is_empty(self) -> bool:
        return self.size == 0

    def flush(self) -> StreamEvent | None:
        """Return a flush event if buffer non-empty, then clear."""
        if self.is_empty:
            return None
        event = self._build_event()
        self._buffer = ""
        return event

    def drain(self) -> StreamEvent | None:
        """Force-flush even if below threshold (final/signal flush)."""
        return self.flush()

    def _build_event(self) -> StreamEvent:
        return StreamEvent(
            event_type="token",
            content=self._buffer,
            done=False,
            token_count=max(1, self._total // 2),
        )


# ====================== Event Model ======================


@dataclass(slots=True)
class StreamEvent:
    """Unified stream event format for both SSE and WebSocket."""

    event_type: str  # stream_id, step, token, tool, error, done
    status: StreamStatus = StreamStatus.GENERATING
    stream_id: str = ""
    message_id: str = ""
    content: str = ""
    step_id: str | None = None
    title: str | None = None
    done: bool = False
    error: str | None = None
    code: str | None = None
    token_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Dispatch table for to_dict — maps event_type -> (key, extractor)
    _SERIALIZERS: ClassVar[dict[str, dict[str, Any]]] = {
        "stream_id": {},
        "step": {
            "step_id": lambda e: e.step_id or "step-unknown",
            "title": lambda e: e.title or "Step",
            "status": lambda e: "active" if e.status == StreamStatus.GENERATING else "done",
            "content": lambda e: e.content,
        },
        "token": {
            "content": lambda e: e.content,
            "response": lambda e: e.content,
            "done": lambda e: e.done,
            "token_count": lambda e: e.token_count,
        },
        "tool": {
            "step_id": lambda e: e.step_id or "tool-unknown",
            "title": lambda e: e.title or "Tool",
            "status": lambda e: "done",
            "content": lambda e: e.content,
        },
        "error": {
            "message": lambda e: e.content,
            "code": lambda e: e.code or "500",
        },
        "done": {
            "done": lambda e: True,
        },
        "resumed": {
            "from_index": lambda e: 0,
        },
    }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for both SSE and WS transport."""
        result: dict[str, Any] = {
            "type": self.event_type,
            "message_id": self.message_id,
            "stream_id": self.stream_id,
            "timestamp": self.timestamp.isoformat(),
        }
        serializer = self._SERIALIZERS.get(self.event_type)
        if serializer:
            for key, extractor in serializer.items():
                result[key] = extractor(self)
        return result

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.to_dict())}\n\n"

    def to_ws(self) -> str:
        return json.dumps(self.to_dict())


# ====================== Prefix-based Event Parser Registry ======================

_EventParser = tuple[str, dict[str, Any] | None]
"""Return type for parser: (content_after_prefix, extra_fields or None)."""


def _parse_prefix(raw: str, prefix: str, delimiter: str = ":") -> _EventParser:
    """Strip prefix and split on delimiter when present."""
    rest = raw[len(prefix):]
    parts = rest.split(delimiter, 1) if delimiter in rest else [rest, ""]
    return parts[0], {}


_PARSERS: dict[str, tuple[str, bool]] = {
    # prefix -> (event_type, has_delimiter)
    "[STREAM_ID]": ("stream_id", False),
    "[RESUME]": ("resumed", True),
    "[STEP]": ("step", True),
    "[TOKEN]": ("token", False),
    "[TOOL]": ("tool", True),
    "[ERROR]": ("error", True),
}


def _parse_event(raw_event: str | dict, message_id: str) -> StreamEvent | None:
    """Parse raw event from LangGraph into StreamEvent."""
    if isinstance(raw_event, dict):
        logger.warning("Dict event from stream_agent received (unexpected): %s", raw_event.get("type", "?"))
        return None

    if not isinstance(raw_event, str):
        return None

    # Fast path: simple sentinels
    if raw_event == "[DONE]":
        return StreamEvent(event_type="done", message_id=message_id)

    # Prefix-based dispatch
    for prefix, (event_type, has_delim) in _PARSERS.items():
        if raw_event.startswith(prefix):
            rest = raw_event[len(prefix) :]
            if has_delim and ":" in rest:
                key, content = rest.split(":", 1)
            else:
                key, content = rest, ""

            if event_type == "stream_id":
                return StreamEvent(
                    event_type="stream_id", stream_id=rest, message_id=message_id
                )
            if event_type == "resumed":
                return StreamEvent(
                    event_type="resumed", stream_id=key, message_id=message_id
                )
            if event_type == "step":
                return StreamEvent(
                    event_type="step",
                    step_id=f"step-{key}",
                    title=key.replace("_", " ").title(),
                    status=StreamStatus.GENERATING,
                    content=content,
                    message_id=message_id,
                )
            if event_type == "token":
                return StreamEvent(
                    event_type="token", content=rest, message_id=message_id
                )
            if event_type == "tool":
                return StreamEvent(
                    event_type="tool",
                    step_id=f"tool-{key}",
                    title=key.replace("_", " ").title(),
                    content=content,
                    message_id=message_id,
                )
            if event_type == "error":
                return StreamEvent(
                    event_type="error",
                    content=content,
                    code=key,
                    message_id=message_id,
                )

    return None


# ====================== Transports ======================


class StreamTransport(ABC):
    """Abstract base class for stream transports."""

    @abstractmethod
    async def send(self, event: StreamEvent) -> bool:
        """Send event to client. Returns False if connection lost."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the transport connection."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        ...


class WebSocketTransport(StreamTransport):
    """WebSocket transport implementation.

    Backpressure is provided by asyncio event loop — send_text() naturally
    blocks when the kernel TCP buffer is full on a slow connection.
    """

    def __init__(self, websocket: WebSocket):
        self._ws = websocket
        self._connected = True
        self._max_buffer = 64  # max queued sends before backpressure

    async def send(self, event: StreamEvent) -> bool:
        try:
            await self._ws.send_text(event.to_ws())
            return True
        except Exception as e:
            logger.debug("WS send error: %s", e)
            self._connected = False
            return False

    async def close(self) -> None:
        with suppress(Exception):
            await self._ws.close()

    @property
    def is_connected(self) -> bool:
        return self._connected


class SSETransport(StreamTransport):
    """SSE transport implementation (writes to queue for StreamingResponse).

    Backpressure is enforced by a bounded asyncio.Queue — when the queue
    reaches maxsize, the producer blocks, preventing unbounded memory growth.
    """

    def __init__(self, max_buffer: int = 64):
        self._queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=max_buffer)
        self._connected = True

    async def send(self, event: StreamEvent) -> bool:
        try:
            await self._queue.put(event.to_sse())
            return True
        except Exception as e:
            logger.debug("SSE send error: %s", e)
            self._connected = False
            return False

    async def close(self) -> None:
        await self._queue.put(None)
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected


# ====================== Unified Streamer ======================


class UnifiedStreamer:
    """
    Unified streaming interface that handles both SSE and WebSocket.

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
        """
        Detect and create appropriate transport based on request.

        Priority:
        1. WebSocket if websocket object provided and connected
        2. SSE otherwise (HTTP request)
        """
        if websocket is not None:
            return WebSocketTransport(websocket)
        return SSETransport()

    async def stream(
        self,
        transport: StreamTransport,
        message: str,
        session_id: str,
        model: str = "",
        provider: str = "ollama",
        temperature: float = 0.7,
        max_attempts: int = 3,
        resume_from: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream events through the unified interface.

        This is the main entry point — handles token buffering,
        event formatting, and proper cleanup.
        """
        async with self._lock:
            self._counter += 1
            stream_id = f"stream-{self._counter}-{uuid.uuid4().hex[:8]}"

        message_id = str(uuid.uuid4())
        buf = _TokenBuffer()

        # Send stream_id event
        yield StreamEvent(
            event_type="stream_id",
            stream_id=stream_id,
            message_id=message_id,
        )

        # Handle resume
        if resume_from:
            yield StreamEvent(
                event_type="resumed",
                stream_id=resume_from,
                message_id=message_id,
            )

        try:
            # Import LangGraph stream
            from backend.domain.core.langgraph import stream_agent as langgraph_stream

            async for raw_event in langgraph_stream(
                message=message,
                session_id=session_id,
                model=model,
                provider=provider,
                max_attempts=max_attempts,
                resume_from=resume_from,
            ):
                if not transport.is_connected:
                    break

                event = _parse_event(raw_event, message_id)
                if not event:
                    continue

                # Handle token buffering and pass-through for other events
                if event.event_type == "token":
                    buf.append(event.content)
                    while buf.is_ready:
                        flush = buf.flush()
                        if flush:
                            yield flush
                else:
                    # Flush pending tokens before non-token events
                    flush = buf.drain()
                    if flush:
                        yield flush

                    yield event

            # Final flush
            flush = buf.drain()
            if flush:
                yield flush

            # Send done
            yield StreamEvent(
                event_type="done",
                message_id=message_id,
            )

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
            yield StreamEvent(
                event_type="done",
                message_id=message_id,
            )

        finally:
            await transport.close()


# ====================== Singleton ======================

_unified_streamer: UnifiedStreamer | None = None


def get_unified_streamer() -> UnifiedStreamer:
    """Get the singleton UnifiedStreamer instance."""
    global _unified_streamer
    if _unified_streamer is None:
        _unified_streamer = UnifiedStreamer()
    return _unified_streamer


# ====================== Convenience: SSE Response ======================


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


# ====================== Legacy Compat ======================


@dataclass(slots=True)
class StreamChunk:
    """Backward-compatible StreamChunk for legacy stream_chat consumers.

    Deprecated: Use StreamEvent directly in new code.
    """

    text: str
    status: StreamStatus
    stream_id: str
    chunk_index: int
    tokens_generated: int = 0
    latency_ms: float = 0.0
    error: str | None = None


async def stream_chat(
    prompt: str,
    model: str = "",
    provider: str = "ollama",
    timeout: int | None = None,
) -> AsyncIterator[StreamChunk]:
    """Legacy API compatibility method — now backed by UnifiedStreamer.

    Wraps UnifiedStreamer.stream() and yields backward-compatible StreamChunk
    objects with .text, .status, etc.

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
    "SSETransport",
    "StreamChunk",
    "StreamEvent",
    "StreamStatus",
    "StreamTransport",
    "UnifiedStreamer",
    "WebSocketTransport",
    "create_sse_response",
    "get_unified_streamer",
    "stream_chat",
]
