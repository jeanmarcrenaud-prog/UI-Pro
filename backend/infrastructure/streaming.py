"""
backend/infrastructure/streaming.py - Streaming Service (LangGraph Version)
Streaming service robuste avec protections async, backpressure,
heartbeat websocket et gestion propre des cancellations.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class StreamStatus(Enum):
    STARTING = "starting"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class StreamChunk:
    text: str
    status: StreamStatus
    stream_id: str
    chunk_index: int
    tokens_generated: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self._map_type(),
            "status": self.status.value,
            "stream_id": self.stream_id,
            "index": self.chunk_index,
            "content": self.text,
            "tokens": self.tokens_generated,
            "latency_ms": round(self.latency_ms, 2),
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }

    def _map_type(self) -> str:
        return {
            StreamStatus.STARTING: "step",
            StreamStatus.GENERATING: "token",
            StreamStatus.COMPLETED: "done",
            StreamStatus.ERROR: "error",
            StreamStatus.CANCELLED: "error",
        }[self.status]


class StreamingService:
    DEFAULT_TIMEOUT = 180  # seconds

    def __init__(self) -> None:
        self._streams: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._counter = 0

    async def stream_generate(
        self,
        generator: AsyncIterator[str],
        websocket: Optional[WebSocket] = None,
        timeout: Optional[int] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        async with self._lock:
            self._counter += 1
            stream_id = f"stream-{self._counter}-{uuid.uuid4().hex[:8]}"

        queue: asyncio.Queue[Optional[StreamChunk]] = asyncio.Queue(maxsize=50)

        producer = asyncio.create_task(
            self._producer(generator, queue, stream_id)
        )

        heartbeat_task = None
        stream_timeout = timeout or self.DEFAULT_TIMEOUT

        try:
            if websocket:
                heartbeat_task = asyncio.create_task(
                    self._heartbeat(websocket, stream_id)
                )

            while True:
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=stream_timeout)
                except asyncio.TimeoutError:
                    logger.warning("stream timeout", extra={"stream_id": stream_id, "timeout": stream_timeout})
                    break

                if chunk is None:
                    break

                payload = chunk.to_dict()

                if websocket:
                    try:
                        await websocket.send_json(payload)
                    except WebSocketDisconnect:
                        logger.info("websocket disconnected", extra={"stream_id": stream_id})
                        break

                yield payload

        except asyncio.CancelledError:
            logger.warning("stream cancelled", extra={"stream_id": stream_id})
            raise

        except Exception:
            logger.exception("streaming failure", extra={"stream_id": stream_id})
            raise

        finally:
            producer.cancel()

            if heartbeat_task:
                heartbeat_task.cancel()

            with suppress(Exception):
                await producer

            if heartbeat_task:
                with suppress(Exception):
                    await heartbeat_task

    async def _producer(
        self,
        generator: AsyncIterator[str],
        queue: asyncio.Queue,
        stream_id: str,
    ) -> None:
        start = time.perf_counter()
        index = 0

        try:
            async for token in generator:
                chunk = StreamChunk(
                    text=token,
                    status=StreamStatus.GENERATING,
                    stream_id=stream_id,
                    chunk_index=index,
                    tokens_generated=index + 1,
                    latency_ms=(time.perf_counter() - start) * 1000,
                )

                await queue.put(chunk)
                index += 1

            await queue.put(
                StreamChunk(
                    text="",
                    status=StreamStatus.COMPLETED,
                    stream_id=stream_id,
                    chunk_index=index,
                )
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            logger.exception("producer error")

            await queue.put(
                StreamChunk(
                    text="",
                    status=StreamStatus.ERROR,
                    stream_id=stream_id,
                    chunk_index=index,
                    error=str(exc),
                )
            )

        finally:
            await queue.put(None)

    async def _heartbeat(self, websocket: WebSocket, stream_id: str) -> None:
        """Heartbeat task that sends periodic pings to keep connection alive."""
        try:
            while True:
                await asyncio.sleep(15)
                await websocket.send_json({"type": "ping", "stream_id": stream_id})
        except (WebSocketDisconnect, asyncio.CancelledError, RuntimeError):
            pass
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}", extra={"stream_id": stream_id})