# services/streaming.py - Real-time Streaming Service
#
# Features:
# - Async generator with proper lifecycle events
# - Guaranteed single final event (done/error/cancelled)
# - Cancellation support
# - Step tracking for frontend
# - Delegates to ModelService/LLMRouter for client creation

import asyncio
import logging
import time
import uuid
from typing import Optional, AsyncIterator, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from models.settings import settings

logger = logging.getLogger(__name__)


class StreamStatus(Enum):
    STARTING = "starting"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class StreamChunk:
    """Standardized streaming chunk for frontend consumption."""
    text: str
    status: StreamStatus
    stream_id: str
    chunk_index: int
    tokens_generated: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None
    step_id: Optional[str] = None
    step_status: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to frontend-compatible format (WebSocket / SSE)"""
        type_map = {
            StreamStatus.STARTING: "token",
            StreamStatus.GENERATING: "token",
            StreamStatus.COMPLETED: "done",
            StreamStatus.ERROR: "error",
            StreamStatus.CANCELLED: "error",
        }

        result: Dict[str, Any] = {
            "type": type_map.get(self.status, "token"),
            "status": self.status.value,
            "stream_id": self.stream_id,
            "index": self.chunk_index,
            "content": self.text,
            "data": self.text,
            "response": self.text,
            "tokens": self.tokens_generated,
            "latency_ms": round(self.latency_ms, 2),
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.step_id:
            result["type"] = "step"
            result["step_id"] = self.step_id
            result["step_status"] = self.step_status

        return result


@dataclass
class StreamConfig:
    """Streaming configuration."""
    chunk_size: int = 5
    max_tokens: int = 4096
    timeout_ms: int = 120_000


class StreamingService:
    """Real-time streaming service with robust lifecycle management."""

    def __init__(self, config: Optional[StreamConfig] = None):
        self.config = config or StreamConfig()
        self._active_streams: Dict[str, Optional[asyncio.Task]] = {}
        self._stream_counter = 0
        self._model_service = None

    def _ensure_model_service(self):
        """Lazy initialization to avoid circular imports."""
        if self._model_service is None:
            from services.model_service import get_model_service
            self._model_service = get_model_service()
        return self._model_service

    def _get_client(self, model: str, provider: Optional[str] = None):
        """
        Get configured client via ModelService.
        
        Fully delegates to ModelService which handles:
        - ModelDiscovery for backend detection
        - LLMRouter for routing
        - Proper URL/endpoint configuration
        
        Falls back to router if ModelService fails.
        """
        model_svc = self._ensure_model_service()

        try:
            return model_svc.get_client_for_model(model=model, provider=provider)
        except (AttributeError, Exception) as e:
            logger.warning(f"ModelService delegation failed: {e}. Falling back to router.")
            from services.llm_router import get_llm_router
            router = get_llm_router()
            mode = "reasoning" if any(k in model.lower() for k in ["deepseek", "qwen", "coder"]) else "fast"
            return router.get_for_mode(mode)

    async def stream_generate(
        self,
        prompt: str,
        model: str,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        on_chunk: Optional[Callable[[StreamChunk], None]] = None,
        start_chunk: int = 0,
    ) -> AsyncIterator[StreamChunk]:
        """
        Main streaming generator with guaranteed final event.
        
        Always yields exactly one final event: COMPLETED, ERROR, or CANCELLED.
        """
        if not model:
            raise ValueError("Model name is required")

        self._stream_counter += 1
        stream_id = f"stream-{self._stream_counter}-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        chunk_index = start_chunk

        current = asyncio.current_task()
        self._active_streams[stream_id] = current if current else None

        # For resume, skip step events
        is_resume = start_chunk > 0

        try:
            client = self._get_client(model, provider)

            # === Step Events (skip on resume) ===
            if not is_resume:
                yield StreamChunk(
                    text="", status=StreamStatus.STARTING, stream_id=stream_id,
                    chunk_index=chunk_index, step_id="step-analyzing", step_status="active"
                )
                chunk_index += 1

                yield StreamChunk(
                    text="", status=StreamStatus.GENERATING, stream_id=stream_id,
                    chunk_index=chunk_index, step_id="step-analyzing", step_status="done"
                )
                chunk_index += 1

                yield StreamChunk(
                    text="", status=StreamStatus.GENERATING, stream_id=stream_id,
                    chunk_index=chunk_index, step_id="step-planning", step_status="active"
                )
                chunk_index += 1

            # === Token Streaming ===
            buffer: list[str] = []
            token_count = 0

            async for chunk_text in self._stream_from_client(client, prompt, model, temperature):
                # Check for cancellation
                task = self._active_streams.get(stream_id)
                if task is not None and task.cancelled():
                    raise asyncio.CancelledError()

                buffer.append(chunk_text)
                token_count += 1

                if len(buffer) >= self.config.chunk_size:
                    full_text = "".join(buffer)
                    chunk = StreamChunk(
                        text=full_text,
                        status=StreamStatus.GENERATING,
                        stream_id=stream_id,
                        chunk_index=chunk_index,
                        tokens_generated=token_count,
                        latency_ms=(time.time() - start_time) * 1000,
                    )
                    if on_chunk:
                        on_chunk(chunk)
                    yield chunk
                    buffer.clear()
                    chunk_index += 1

                if token_count >= self.config.max_tokens:
                    break

            # Flush remaining buffer
            if buffer:
                chunk = StreamChunk(
                    text="".join(buffer),
                    status=StreamStatus.GENERATING,
                    stream_id=stream_id,
                    chunk_index=chunk_index,
                    tokens_generated=token_count,
                    latency_ms=(time.time() - start_time) * 1000,
                )
                if on_chunk:
                    on_chunk(chunk)
                yield chunk
                chunk_index += 1

            # === Guaranteed Final Event ===
            final = StreamChunk(
                text="",
                status=StreamStatus.COMPLETED,
                stream_id=stream_id,
                chunk_index=chunk_index,
                tokens_generated=token_count,
                latency_ms=(time.time() - start_time) * 1000,
            )
            if on_chunk:
                on_chunk(final)
            yield final

        except asyncio.CancelledError:
            logger.info(f"Stream {stream_id} was cancelled")
            cancelled = StreamChunk(
                text="", status=StreamStatus.CANCELLED, stream_id=stream_id,
                chunk_index=chunk_index, error="Request cancelled by user"
            )
            if on_chunk:
                on_chunk(cancelled)
            yield cancelled

        except Exception as e:
            logger.error(f"Streaming failed for stream {stream_id}", exc_info=True)
            error_chunk = StreamChunk(
                text="", status=StreamStatus.ERROR, stream_id=stream_id,
                chunk_index=chunk_index, error=str(e)
            )
            if on_chunk:
                on_chunk(error_chunk)
            yield error_chunk

        finally:
            self._active_streams.pop(stream_id, None)

    async def _stream_from_client(self, client, prompt: str, model: str, temperature: float):
        """Helper to support both sync and async streaming clients."""
        # Check if client has stream method
        if not hasattr(client, 'stream'):
            logger.warning("Client has no stream method, using generate")
            result = client.generate(prompt=prompt, model=model, temperature=temperature)
            yield result
            return

        # Handle async vs sync
        stream_method = client.stream
        if asyncio.iscoroutinefunction(stream_method):
            async for chunk in stream_method(prompt=prompt, model=model, temperature=temperature):
                yield chunk
        else:
            # Synchronous client wrapped
            for chunk in stream_method(prompt=prompt, model=model, temperature=temperature):
                yield chunk

    def cancel_stream(self, stream_id: str) -> bool:
        """Cancel an active stream."""
        task = self._active_streams.get(stream_id)
        if task and not task.cancelled():
            task.cancel()
            logger.debug(f"Cancellation requested for stream {stream_id}")
            return True
        return False

    def get_active_count(self) -> int:
        return len(self._active_streams)


# ====================== Singleton ======================

_streaming_service: Optional[StreamingService] = None


def get_streaming_service() -> StreamingService:
    global _streaming_service
    if _streaming_service is None:
        _streaming_service = StreamingService()
    return _streaming_service


__all__ = [
    "StreamingService",
    "StreamChunk",
    "StreamConfig",
    "StreamStatus",
    "get_streaming_service"
]