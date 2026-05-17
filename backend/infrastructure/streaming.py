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

# Token counting with tiktoken
_token_encoder = None

def _get_encoder():
    """Lazy load tiktoken encoder."""
    global _token_encoder
    if _token_encoder is None:
        try:
            import tiktoken
            # Use cl100k_base for most models (GPT-4, Qwen, etc.)
            _token_encoder = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"tiktoken not available: {e}")
            return None
    return _token_encoder

def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    encoder = _get_encoder()
    if encoder:
        try:
            return len(encoder.encode(text))
        except Exception:
            pass
    # Fallback: ~4 chars per token
    return len(text) // 4


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
    HEARTBEAT_INTERVAL = 15  # seconds

    def __init__(self) -> None:
        self._streams: Dict[str, asyncio.Task] = {}  # For future tracking
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

        # Track stream for future metrics
        task = asyncio.current_task()
        if task:
            self._streams[stream_id] = task

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
                    logger.warning("Stream timeout", extra={"stream_id": stream_id, "timeout": stream_timeout})
                    break

                if chunk is None:
                    break

                payload = chunk.to_dict()

                if websocket:
                    try:
                        await websocket.send_json(payload)
                    except (WebSocketDisconnect, RuntimeError):
                        logger.info("WebSocket disconnected", extra={"stream_id": stream_id})
                        break
                    except Exception as e:
                        logger.warning(f"Send error: {e}", extra={"stream_id": stream_id})

                yield payload

        except asyncio.CancelledError:
            logger.info("Stream cancelled by client", extra={"stream_id": stream_id})
            raise

        except Exception as e:
            logger.exception("Streaming failure", extra={"stream_id": stream_id})
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

            # Cleanup
            self._streams.pop(stream_id, None)

    async def _producer(
        self,
        generator: AsyncIterator[str],
        queue: asyncio.Queue,
        stream_id: str,
    ) -> None:
        start = time.perf_counter()
        index = 0
        accumulated_text = ""

        try:
            async for token in generator:
                accumulated_text += token
                token_count = count_tokens(accumulated_text)
                
                chunk = StreamChunk(
                    text=token,
                    status=StreamStatus.GENERATING,
                    stream_id=stream_id,
                    chunk_index=index,
                    tokens_generated=token_count,
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
                    tokens_generated=count_tokens(accumulated_text),
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
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                await websocket.send_json({"type": "ping", "stream_id": stream_id})
        except (WebSocketDisconnect, asyncio.CancelledError, RuntimeError):
            pass
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}", extra={"stream_id": stream_id})