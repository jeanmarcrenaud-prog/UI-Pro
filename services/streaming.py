# services/streaming.py
"""
Streaming Service for real-time LLM responses.

Features:
- Async generator with proper lifecycle events
- Guaranteed single final event (done/error/cancelled)
- Cancellation support
- Step tracking for frontend
- Backend detection and validation
"""

import asyncio
import logging
import time
import uuid
from typing import Optional, AsyncIterator, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class StreamStatus(Enum):
    STARTING = "starting"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class StreamChunk:
    """Represents a single chunk in the streaming response."""
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

    def to_dict(self) -> dict[str, Any]:
        """Convert to frontend-compatible format (WebSocket / SSE)"""
        type_map = {
            StreamStatus.STARTING: "token",
            StreamStatus.GENERATING: "token",
            StreamStatus.COMPLETED: "done",
            StreamStatus.ERROR: "error",
            StreamStatus.CANCELLED: "error",
        }

        result: dict[str, Any] = {
            "type": type_map.get(self.status, "token"),
            "status": self.status.value,
            "stream_id": self.stream_id,
            "index": self.chunk_index,
            "data": self.text,
            "content": self.text,
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
    chunk_size: int = 5
    max_tokens: int = 4096
    timeout_ms: int = 120_000
    enable_progress: bool = True

    backend_rules: dict[str, list[str]] = field(default_factory=lambda: {
        "ollama": [],
        "lemonade": ["GGUF", "user.", "Whisper"],
        "llamacpp": ["llamacpp"],
        "lmstudio": ["lmstudio"],
    })


class StreamingService:
    def __init__(self, config: Optional[StreamConfig] = None):
        self.config = config or StreamConfig()
        self._active_streams: Dict[str, asyncio.Task] = {}
        self._stream_counter = 0

    def _detect_backend(self, model: str) -> str:
        """Detect backend based on model name patterns."""
        for backend, patterns in self.config.backend_rules.items():
            if any(pattern in model or model.startswith(pattern) for pattern in patterns):
                return backend
        return "ollama"

    def _get_client(self, model: str, provider: str | None = None):
        """Get appropriate client for the model/backend."""
        from llm.router import OllamaClient, ModelConfig
        from models.settings import settings

        # Use provider if explicitly provided, otherwise detect from model name
        backend = provider if provider else self._detect_backend(model)
        
        # Map common provider names to backend keys
        backend_mapping = {
            "lmstudio": "lmstudio",
            "lemonade": "lemonade",
            "llamacpp": "llamacpp",
            "ollama": "ollama",
        }
        backend_key = backend_mapping.get(backend.lower() if backend else "ollama", "ollama")
        
        logger.info(f"[streaming] _get_client: model={model}, provider={provider}, backend={backend}, backend_key={backend_key}")
        
        backend_cfg = settings.backends.get(backend_key)

        # Smart fallback: if provider is explicitly lmstudio/lemonade, try to use it even if not in enabled list
        if backend_key in ("lmstudio", "lemonade") and provider:
            lmstudio_cfg = settings.backends.get("lmstudio")
            lemonade_cfg = settings.backends.get("lemonade")
            if backend_key == "lmstudio" and lmstudio_cfg:
                url = lmstudio_cfg.get("url", settings.lmstudio_url)
            elif backend_key == "lemonade" and lemonade_cfg:
                url = lemonade_cfg.get("url", settings.lemonade_url)
            else:
                url = settings.lmstudio_url if backend_key == "lmstudio" else settings.lemonade_url
        elif not backend_cfg or not backend_cfg.get("enabled", False):
            # Fallback: try lmstudio as secondary if ollama not enabled
            lmstudio_cfg = settings.backends.get("lmstudio")
            if lmstudio_cfg and lmstudio_cfg.get("enabled", False):
                url = lmstudio_cfg.get("url", settings.lmstudio_url)
            else:
                url = settings.ollama_url
        else:
            url = backend_cfg["url"]
        
        logger.info(f"[streaming] Using URL: {url} for model {model}")

        config = ModelConfig(
            url=f"{url}/api/generate",
            model=model,
            timeout=self.config.timeout_ms // 1000
        )
        return OllamaClient(config)

    async def stream_generate(
        self,
        prompt: str,
        model: str,
        provider: str | None = None,
        start_chunk: int = 0,
        temperature: float = 0.7,
        on_chunk: Optional[Callable[[StreamChunk], None]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Main streaming generator.
        Always yields exactly one final event: COMPLETED, ERROR, or CANCELLED.
        
        Args:
            prompt: The prompt to send to the model
            model: Model name
            provider: Backend provider (ollama, lmstudio, lemonade, etc.)
            start_chunk: Chunk index to start from (for resume) - skips step events if > 0
            temperature: Model temperature
            on_chunk: Optional callback for each chunk
        """
        if not model:
            raise ValueError("Model name is required")

        self._stream_counter += 1
        stream_id = f"stream-{self._stream_counter}-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        chunk_index = start_chunk  # Start from resume position

        self._active_streams[stream_id] = asyncio.current_task()
        
        # For resume, skip step events and start directly from token streaming
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

            for chunk_text in client.stream(prompt=prompt, model=model, temperature=temperature):
                # Check for cancellation
                if self._active_streams.get(stream_id) and self._active_streams[stream_id].cancelled():
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

            # Flush any remaining tokens
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

            # === SUCCESS: Single final completed event ===
            final_chunk = StreamChunk(
                text="",
                status=StreamStatus.COMPLETED,
                stream_id=stream_id,
                chunk_index=chunk_index,
                tokens_generated=token_count,
                latency_ms=(time.time() - start_time) * 1000,
            )
            if on_chunk:
                on_chunk(final_chunk)
            yield final_chunk

        except asyncio.CancelledError:
            logger.info(f"Stream {stream_id} was cancelled")
            cancelled_chunk = StreamChunk(
                text="", status=StreamStatus.CANCELLED, stream_id=stream_id,
                chunk_index=chunk_index, error="Request cancelled by user"
            )
            if on_chunk:
                on_chunk(cancelled_chunk)
            yield cancelled_chunk

        except Exception as e:
            logger.error(f"Streaming failed for stream {stream_id}", exc_info=True)
            error_chunk = StreamChunk(
                text="",
                status=StreamStatus.ERROR,
                stream_id=stream_id,
                chunk_index=chunk_index,
                error=str(e)
            )
            if on_chunk:
                on_chunk(error_chunk)
            yield error_chunk

        finally:
            # Always clean up
            self._active_streams.pop(stream_id, None)

    def cancel_stream(self, stream_id: str) -> bool:
        """Cancel an active streaming task."""
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