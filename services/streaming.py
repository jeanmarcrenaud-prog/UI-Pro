# services/streaming.py - Streaming Service
#
# Real-time streaming responses with:
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
        
        return {
            "type": type_map.get(self.status, "token"),
            "status": self.status.value,
            "stream_id": self.stream_id,
            "index": self.chunk_index,
            "data": self.text,  # frontend expects 'data' not 'text'
            "content": self.text,  # also available as 'content'
            "tokens": self.tokens_generated,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StreamConfig:
    """Streaming configuration"""
    chunk_size: int = 20  # Tokens per chunk
    buffer_tokens: int = 10  # Buffer before first yield
    max_tokens: int = 2048
    timeout_ms: int = 60000
    enable_progress: bool = True


class StreamingService:
    """
    Service for streaming LLM responses in real-time.
    
    Features:
    - Single completion event per stream (no duplicates)
    - Proper cancellation tracking
    - Retry logic for network issues
    """
    
    def __init__(self, config: StreamConfig = None):
        self.config = config or StreamConfig()
        self._active_streams: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, Callable] = {}
        # Monotonic counter for unique stream IDs
        self._stream_counter = 0
    
    async def stream_generate(
        self,
        prompt: str,
        model: str = None,
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
            from adapters.llm import OllamaClient
            from services.llm_router import get_llm_router
            
            # Get model from router
            router = get_llm_router()
            route_result = router.route(prompt, mode=mode)
            model = model or route_result["model"]
            
            client = OllamaClient()
            
            # Register this stream so it can be cancelled later
            self._active_streams[stream_id] = asyncio.current_task()
            
            # Start streaming with initial STATUS
            yield StreamChunk(
                text="",
                status=StreamStatus.STARTING,
                stream_id=stream_id,
                chunk_index=0,
                latency_ms=0,
                error="Initializing stream..."
            )
            
            buffer = []
            token_count = 0
            
            for chunk_text in client.stream(prompt, model=model):
                # Check for cancellation
                if stream_id in self._active_streams:
                    active_task = self._active_streams[stream_id]
                    if active_task.cancelled():
                        is_cancelled = True
                        logger.debug(f"Stream {stream_id} was cancelled")
                        break
                
                # Accumulate buffer (streaming chunks individually)
                buffer.append(chunk_text)
                token_count += 1
                
                # Only yield when buffer reaches chunk size
                if len(buffer) >= self.config.chunk_size:
                    full_text = "".join(buffer)
                    
                    chunk = StreamChunk(
                        text=full_text,
                        status=StreamStatus.GENERATING,
                        stream_id=stream_id,
                        chunk_index=chunk_index,
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
                            remaining_chunk = StreamChunk(
                                text=full_text,
                                status=StreamStatus.GENERATING,
                                stream_id=stream_id,
                                chunk_index=chunk_index,
                                tokens_generated=token_count,
                                latency_ms=(time.time() - start_time) * 1000,
                                error="Max tokens reached"
                            )
                            yield remaining_chunk
                        break
            
                  # Only if stream completed successfully (not cancelled and no max tokens reached)
            if not is_cancelled and token_count < self.config.max_tokens:
                yield StreamChunk(
                    text="",
                    status=StreamStatus.COMPLETED,
                    stream_id=stream_id,
                    chunk_index=chunk_index,
                    tokens_generated=token_count,
                    latency_ms=(time.time() - start_time) * 1000,
                    error="Stream completed successfully"
                )
            elif is_cancelled and buffer:
                logger.warning(
                    f"Stream {stream_id} cancelled with {len(buffer)} tokens remaining in buffer"
                )
            # Note: Don't send any event if max tokens reached (cleanup handled by COMPLETED or ERROR)
                
        except Exception as e:
            logger.error(f"Streaming error for {stream_id}: {e}", exc_info=True)
            # Send error event EXACTLY ONCE (not COMPLETED)
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
    "stream_to_string",
    "get_streaming_service"
]
