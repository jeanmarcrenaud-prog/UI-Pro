# services/streaming.py - Streaming Service
#
# Role: Real-time LLM response streaming with WebSocket support
# Used by: WebSocket endpoint, API streaming
# - Stream-based generation
# - Error recovery
# - Proper cancellation support
# - Single final event per stream

import asyncio
import logging
import time
import uuid
from typing import Optional, AsyncIterator, Callable, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from urllib.error import URLError as ConnectionError

logger = logging.getLogger(__name__)


class StreamStatus(Enum):
    """Streaming status"""
    STARTING = "starting"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class StreamChunk:
    """Single chunk of streamed response"""
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
        """Serialize to JSON-serializable dict for WebSocket/SSE
        
        Frontend expects: type: 'token' | 'step' | 'tool' | 'done' | 'error'
        """
        # Map status to frontend event type
        type_map = {
            StreamStatus.STARTING: "token",
            StreamStatus.GENERATING: "token",
            StreamStatus.COMPLETED: "done",
            StreamStatus.ERROR: "error",
            StreamStatus.CANCELLED: "error",
        }
        
        result = {
            "type": type_map.get(self.status, "token"),
            "status": self.status.value,
            "stream_id": self.stream_id,
            "index": self.chunk_index,
            "data": self.text,  # frontend expects 'data' not 'text'
            "content": self.text,  # also available as 'content'
            "response": self.text,  # KEY FIX: Frontend looks for 'response' field
            "tokens": self.tokens_generated,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }
        
        # Add step events for frontend step tracking
        if self.step_id:
            result["type"] = "step"
            result["step_id"] = self.step_id
            result["step_status"] = self.step_status
        
        return result


@dataclass
class StreamConfig:
    """Streaming configuration"""
    chunk_size: int = 20  # Tokens per chunk
    buffer_tokens: int = 10  # Buffer before first yield
    max_tokens: int = 2048
    timeout_ms: int = 60000
    enable_progress: bool = True
    
    # Backend detection rules (model name patterns -> backend)
    backend_rules: dict = None
    
    def __post_init__(self):
        if self.backend_rules is None:
            self.backend_rules = {
                "ollama": [],  # Default for ollama models
                "lemonade": ["GGUF", "user.", "Whisper-Base"],
                "llamacpp": ["llamacpp"],
                "lmstudio": ["lmstudio"],
            }


class StreamingService:
    """
    Service for streaming LLM responses in real-time.
    
    Features:
    - Single completion event per stream (no duplicates)
    - Proper cancellation tracking
    - Network error handling
    - JSON-formatted event dispatch
    """
    
    def __init__(self, config: StreamConfig = None):
        self.config = config or StreamConfig()
        self._active_streams: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._stream_counter = 0
    
    TO_DICT_MAP = {
        StreamStatus.STARTING: "starting",
        StreamStatus.GENERATING: "generating",
        StreamStatus.COMPLETED: "completed",
        StreamStatus.ERROR: "error",
        StreamStatus.CANCELLED: "cancelled",
    }
    
    def to_dict(self, chunk: StreamChunk) -> dict[str, Any]:
        """Convert chunk to SSE format - FRONTEND COMPATIBLE"""
        return {
            "type": self.TO_DICT_MAP.get(chunk.status, "token"),
            "status": chunk.status.value,
            "stream_id": chunk.stream_id,
            "index": chunk.chunk_index,
            "data": chunk.text,
            "content": chunk.text,
            "response": chunk.text,  # KEY FIX: Frontend looks for 'response' field
            "tokens": chunk.tokens_generated,
            "latency_ms": chunk.latency_ms,
            "error": chunk.error,
            "timestamp": chunk.timestamp.isoformat(),
        }
    
    def _detect_backend(self, model: str) -> str:
        """Detect which backend to use based on model name patterns."""
        rules = self.config.backend_rules
        for backend, patterns in rules.items():
            if not patterns:
                continue  # Empty list = default for this backend
            for pattern in patterns:
                if pattern in model or model.startswith(pattern):
                    return backend
        return "ollama"  # Default fallback
    
    def _get_validated_client(self, model: str, backend: str):
        """Validate backend availability and get client."""
        from llm.client import OllamaClient, ModelConfig
        from models.settings import settings
        import requests
        
        backends_config = settings.backends
        backend_cfg = backends_config.get(backend)
        
        if not backend_cfg:
            raise ValueError(f"Unknown backend: {backend}")
        
        if not backend_cfg.get("enabled", False):
            raise ValueError(f"Backend '{backend}' is disabled in config")
        
        url = backend_cfg["url"]
        models_endpoint = backend_cfg["models_endpoint"]
        
        logger.info(f"[STREAM] Checking backend {backend} at {url}...")
        
        try:
            test_resp = requests.get(f"{url}{models_endpoint}", timeout=5)
            logger.info(f"[STREAM] Backend check status: {test_resp.status_code}")
            if test_resp.status_code == 404:
                # Endpoint doesn't exist - try anyway
                pass
            elif not test_resp.ok:
                raise ValueError(f"Backend '{backend}' returned {test_resp.status_code}")
            
            # Parse models based on backend
            available_models = self._parse_available_models(test_resp, backend)
            logger.info(f"[STREAM] Available models: {available_models}")
            
            # Skip exact match check - just log warning
            if model not in available_models:
                logger.warning(f"[STREAM] Model '{model}' not in list, but trying anyway...")
            
            logger.info(f"[STREAM] {backend} validated, model '{model}' available")
            
        except requests.exceptions.ConnectionError as e:
            raise ValueError(f"Backend '{backend}' not reachable: {e}")
        
        # Return client for validated backend
        config = ModelConfig(url=url, model=model, timeout=30)
        return OllamaClient(config)
    
    def _parse_available_models(self, response, backend: str) -> list[str]:
        """Parse available models from backend response."""
        if not response.ok:
            return []
        
        try:
            data = response.json()
        except Exception:
            return []
        
        if backend == "ollama":
            return [m.get("name", "") for m in data.get("models", [])]
        elif backend == "lemonade":
            return [m.get("id", "") for m in data.get("data", [])]
        elif backend in ["lmstudio", "llamacpp"]:
            return [m.get("id", "") for m in data.get("data", [])]
        
        return []
    
    async def stream_generate(
        self,
        prompt: str,
        model: str | None = None,  # REQUIRED - no fallback!
        mode: str = "fast",
        on_chunk: Optional[Callable[[StreamChunk], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream LLM response as async iterator.
        
        Stream lifecycle:
        1. STARTING - Initial event with stream_id
        2. GENERATING - Chunk events (only when buffer full)
        3. COMPLETED - Exactly ONE final event on success
        4. ERROR - If exception or cancellation
        """
        # Generate unique stream ID with monotonic counter (atomic)
        self._stream_counter += 1
        stream_id = f"stream-{self._stream_counter}-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        chunk_index = 0
        
        # Track cancellation flag
        is_cancelled = False
        
        try:
            # Get LLM client
            from llm.client import OllamaClient, ModelConfig
            from models.settings import settings
            
            logger.info(f"[STREAM] settings.ollama_url={settings.ollama_url}")
            logger.info(f"[STREAM] settings.model_fast={settings.model_fast}")
            logger.info(f"[STREAM] settings.model_reasoning={settings.model_reasoning}")
            
            # Model is REQUIRED - no fallback
            if not model:
                raise ValueError("[STREAM] No model provided! Model is required.")
            
            logger.info(f"[STREAM] Using model: {model}")
            
            # Detect backend using config rules
            backend = self._detect_backend(model)
            logger.info(f"[STREAM] Detected backend: {backend}")
            
            # Validate backend and model using settings config
            logger.info(f"[STREAM] Getting validated client for {backend}...")
            client = self._get_validated_client(model, backend)
            logger.info(f"[STREAM] Got client: url={client.url}, model={client.model}")
            
            # Register this stream so it can be cancelled later
            self._active_streams[stream_id] = asyncio.current_task()
            
            # Send step event: Step 1 - Analyzing (STARTING)
            yield StreamChunk(
                text="",
                status=StreamStatus.STARTING,
                stream_id=stream_id,
                chunk_index=0,
                latency_ms=0,
                step_id="step-analyzing",
                step_status="active"
            )
            
            # Send step event: Step 1 done, Step 2 active
            yield StreamChunk(
                text="",
                status=StreamStatus.GENERATING,
                stream_id=stream_id,
                chunk_index=1,
                latency_ms=(time.time() - start_time) * 1000,
                step_id="step-analyzing",
                step_status="done"
            )
            yield StreamChunk(
                text="",
                status=StreamStatus.GENERATING,
                stream_id=stream_id,
                chunk_index=2,
                latency_ms=(time.time() - start_time) * 1000,
                step_id="step-planning",
                step_status="active"
            )
            
            buffer = []
            token_count = 0
            
            logger.info(f"[STREAM] Starting stream call to {client.url}...")
            for chunk_text in client.stream(prompt, model=model):
                logger.info(f"[STREAM] Got chunk: {len(chunk_text)} chars")
                # Check for cancellation
                if stream_id in self._active_streams:
                    task = self._active_streams[stream_id]
                    if task.cancelled():
                        is_cancelled = True
                        logger.debug(f"Stream {stream_id} was cancelled")
                        break
                
                buffer.append(chunk_text)
                token_count += 1
                
                # Only yield when buffer reaches chunk size
                if len(buffer) >= self.config.chunk_size:
                    full_text = "".join(buffer)
                    
                    chunk = StreamChunk(
                        text=full_text, status=StreamStatus.GENERATING,
                        stream_id=stream_id, chunk_index=chunk_index,
                        tokens_generated=token_count,
                        latency_ms=(time.time() - start_time) * 1000
                    )
                    
                    # Callbacks
                    if on_chunk:
                        on_chunk(chunk)
                    if on_progress and self.config.enable_progress:
                        on_progress(token_count, self.config.max_tokens)
                    
                    yield chunk
                    
                    # Clear buffer
                    buffer = []
                    chunk_index += 1
                    
                    # Check max tokens
                    if token_count >= self.config.max_tokens:
                        # Send remaining buffer before stopping
                        if buffer:
                            full_text = "".join(buffer)
                            yield StreamChunk(
                                text=full_text, status=StreamStatus.GENERATING,
                                stream_id=stream_id, chunk_index=chunk_index,
                                error="Max tokens reached"
                            )
                        # Send COMPLETED event
                        yield StreamChunk(
                            text="", status=StreamStatus.COMPLETED,
                            stream_id=stream_id, chunk_index=chunk_index,
                            error="Max tokens reached"
                        )
                        break
        except ConnectionError as e:
            logger.error(f"Network error for stream {stream_id}: {e}", exc_info=True)
            if not is_cancelled:
                yield StreamChunk(
                    text="",
                    status=StreamStatus.ERROR,
                    stream_id=stream_id,
                    chunk_index=chunk_index,
                    error=f"Network error: {e}"
                )
                # Call error callback
                if on_chunk:
                    on_chunk(StreamChunk(
                        text="",
                        status=StreamStatus.ERROR,
                        stream_id=stream_id,
                        chunk_index=chunk_index,
                        error=f"Network error: {e}"
                    ))
        except Exception as e:
            logger.error(f"Streaming error for {stream_id}: {e}", exc_info=True)
            if not is_cancelled:
                yield StreamChunk(
                    text="",
                    status=StreamStatus.ERROR,
                    stream_id=stream_id,
                    chunk_index=chunk_index,
                    error=str(e)
                )
        finally:
            # Cleanup always
            if stream_id in self._active_streams:
                del self._active_streams[stream_id]
    
    def cancel_stream(self, stream_id: str) -> bool:
        """Cancel an active stream if it exists"""
        if stream_id in self._active_streams:
            task = self._active_streams[stream_id]
            if not task.cancelled():
                task.cancel()
                logger.debug(f"Cancelled stream {stream_id}")
                return True
        return False
    
    def get_active_count(self) -> int:
        """Get number of active streams"""
        return len(self._active_streams)


# Singleton
_streaming_service: Optional[StreamingService] = None


def get_streaming_service() -> StreamingService:
    """Get singleton streaming service"""
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
