"""
backend/infrastructure/streaming_unified.py - Unified Streaming Protocol

Hybrid SSE + WebSocket streaming with auto-detection of client capability.
Provides a single interface that routes to SSE or WS based on transport.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, Optional, Union

from fastapi import WebSocket, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


class StreamStatus(Enum):
    STARTING = "starting"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class StreamEvent:
    """Unified stream event format for both SSE and WebSocket."""
    event_type: str  # stream_id, step, token, tool, error, done
    status: StreamStatus = StreamStatus.GENERATING
    stream_id: str = ""
    message_id: str = ""
    content: str = ""
    step_id: Optional[str] = None
    title: Optional[str] = None
    done: bool = False
    error: Optional[str] = None
    code: Optional[str] = None
    token_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for both SSE and WS transport."""
        result: Dict[str, Any] = {
            "type": self.event_type,
            "message_id": self.message_id,
            "stream_id": self.stream_id,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.event_type == "stream_id":
            pass  # Only type + stream_id + message_id

        elif self.event_type == "step":
            result["step_id"] = self.step_id or "step-unknown"
            result["title"] = self.title or "Step"
            result["status"] = "active" if self.status == StreamStatus.GENERATING else "done"
            result["content"] = self.content

        elif self.event_type == "token":
            result["content"] = self.content
            result["response"] = self.content
            result["done"] = self.done
            result["token_count"] = self.token_count

        elif self.event_type == "tool":
            result["step_id"] = self.step_id or "tool-unknown"
            result["title"] = self.title or "Tool"
            result["status"] = "done"
            result["content"] = self.content

        elif self.event_type == "error":
            result["message"] = self.content
            result["code"] = self.code or "500"

        elif self.event_type == "done":
            result["done"] = True

        elif self.event_type == "resumed":
            result["from_index"] = 0

        return result

    def to_sse(self) -> str:
        """Convert to SSE format."""
        return f"data: {json.dumps(self.to_dict())}\n\n"

    def to_ws(self) -> str:
        """Convert to WebSocket JSON format."""
        return json.dumps(self.to_dict())


class StreamTransport(ABC):
    """Abstract base class for stream transports."""

    @abstractmethod
    async def send(self, event: StreamEvent) -> bool:
        """Send event to client. Returns False if connection lost."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the transport connection."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        pass


class WebSocketTransport(StreamTransport):
    """WebSocket transport implementation."""

    def __init__(self, websocket: WebSocket):
        self._ws = websocket
        self._connected = True

    async def send(self, event: StreamEvent) -> bool:
        try:
            await self._ws.send_text(event.to_ws())
            return True
        except Exception as e:
            logger.debug(f"WS send error: {e}")
            self._connected = False
            return False

    async def close(self) -> None:
        with suppress(Exception):
            await self._ws.close()

    @property
    def is_connected(self) -> bool:
        return self._connected


class SSETransport(StreamTransport):
    """SSE transport implementation (writes to queue for StreamingResponse)."""

    def __init__(self):
        self._queue: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=100)
        self._connected = True

    async def send(self, event: StreamEvent) -> bool:
        try:
            await self._queue.put(event.to_sse())
            return True
        except Exception as e:
            logger.debug(f"SSE send error: {e}")
            self._connected = False
            return False

    async def close(self) -> None:
        await self._queue.put(None)
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected


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
        request: Optional[Request] = None,
        websocket: Optional[WebSocket] = None,
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
        resume_from: Optional[str] = None,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream events through the unified interface.

        This is the main entry point - handles token buffering,
        event formatting, and proper cleanup.
        """
        async with self._lock:
            self._counter += 1
            stream_id = f"stream-{self._counter}-{uuid.uuid4().hex[:8]}"

        message_id = str(uuid.uuid4())

        # Token buffering for chunking
        CHUNK_THRESHOLD = 20  # chars ~5 tokens
        token_buffer = ""
        accumulated_content = ""

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

                # Parse and convert events
                event = self._parse_event(raw_event, message_id)
                if not event:
                    continue

                # Handle token buffering
                if event.event_type == "token":
                    token_buffer += event.content
                    accumulated_content += event.content

                    if len(token_buffer) >= CHUNK_THRESHOLD:
                        event.content = token_buffer
                        event.token_count = max(1, len(accumulated_content) // 2)
                        yield event
                        token_buffer = ""
                else:
                    # Flush token buffer before non-token events
                    if token_buffer:
                        flush_event = StreamEvent(
                            event_type="token",
                            content=token_buffer,
                            done=False,
                            message_id=message_id,
                            token_count=max(1, len(accumulated_content) // 2),
                        )
                        yield flush_event
                        token_buffer = ""
                        accumulated_content = ""

                    yield event

            # Flush remaining tokens
            if token_buffer:
                yield StreamEvent(
                    event_type="token",
                    content=token_buffer,
                    done=False,
                    message_id=message_id,
                    token_count=max(1, len(accumulated_content + token_buffer) // 2),
                )

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

    def _parse_event(
        self,
        raw_event: Union[str, Dict],
        message_id: str,
    ) -> Optional[StreamEvent]:
        """Parse raw event from LangGraph into StreamEvent."""
        if isinstance(raw_event, dict):
            # Already formatted
            return None  # Pass through as-is

        if not isinstance(raw_event, str):
            return None

        # Parse string events from LangGraph
        if raw_event.startswith("[STREAM_ID]"):
            return StreamEvent(
                event_type="stream_id",
                stream_id=raw_event[11:],
                message_id=message_id,
            )

        if raw_event.startswith("[RESUME]"):
            parts = raw_event[7:].split(":")
            return StreamEvent(
                event_type="resumed",
                stream_id=parts[0] if parts else "",
                message_id=message_id,
            )

        if raw_event.startswith("[STEP]"):
            parts = raw_event[6:].split(":", 1)
            phase = parts[0] if parts else "step"
            content = parts[1] if len(parts) > 1 else ""
            return StreamEvent(
                event_type="step",
                step_id=f"step-{phase}",
                title=phase.replace("_", " ").title(),
                status=StreamStatus.GENERATING,
                content=content,
                message_id=message_id,
            )

        if raw_event.startswith("[TOKEN]"):
            return StreamEvent(
                event_type="token",
                content=raw_event[7:],
                message_id=message_id,
            )

        if raw_event.startswith("[TOOL]"):
            parts = raw_event[6:].split(":", 1)
            action = parts[0] if parts else "tool"
            content = parts[1] if len(parts) > 1 else ""
            return StreamEvent(
                event_type="tool",
                step_id=f"tool-{action}",
                title=action.replace("_", " ").title(),
                content=content,
                message_id=message_id,
            )

        if raw_event.startswith("[ERROR]"):
            parts = raw_event[7:].split(":", 1)
            code = parts[0] if parts else "500"
            content = parts[1] if len(parts) > 1 else ""
            return StreamEvent(
                event_type="error",
                content=content,
                code=code,
                message_id=message_id,
            )

        if raw_event == "[DONE]":
            return StreamEvent(
                event_type="done",
                message_id=message_id,
            )

        return None


# Singleton instance
_unified_streamer: Optional[UnifiedStreamer] = None


def get_unified_streamer() -> UnifiedStreamer:
    """Get the singleton UnifiedStreamer instance."""
    global _unified_streamer
    if _unified_streamer is None:
        _unified_streamer = UnifiedStreamer()
    return _unified_streamer


# Convenience function for SSE endpoint
async def create_sse_response(
    message: str,
    model: str,
    provider: str,
    temperature: float,
    session_id: Optional[str] = None,
    resume_from: Optional[str] = None,
) -> StreamingResponse:
    """Create SSE StreamingResponse using unified streamer."""
    session_id = session_id or str(uuid.uuid4())[:8]
    streamer = get_unified_streamer()
    transport = SSETransport()

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


__all__ = [
    "UnifiedStreamer",
    "get_unified_streamer",
    "StreamEvent",
    "StreamTransport",
    "WebSocketTransport",
    "SSETransport",
    "create_sse_response",
]