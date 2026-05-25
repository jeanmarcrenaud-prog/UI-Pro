"""
Stream transports: abstract base + WebSocket + SSE implementations.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import suppress

from fastapi import WebSocket

from backend.infrastructure.streaming.models import StreamEvent

logger = logging.getLogger(__name__)


class StreamTransport(ABC):
    """Abstract base class for stream transports."""

    @abstractmethod
    async def send(self, event: StreamEvent) -> bool:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...


class WebSocketTransport(StreamTransport):
    """WebSocket transport implementation.

    Backpressure is provided by asyncio event loop — send_text() naturally
    blocks when the kernel TCP buffer is full on a slow connection.
    """

    def __init__(self, websocket: WebSocket):
        self._ws = websocket
        self._connected = True

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


__all__ = [
    "SSETransport",
    "StreamTransport",
    "WebSocketTransport",
]
