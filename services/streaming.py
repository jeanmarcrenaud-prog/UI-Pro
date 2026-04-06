# services/streaming.py - Streaming Service
#
# Real-time streaming responses with:
# - Chunk-based generation
# - Progress tracking
# - Error recovery
# - Queue management

import asyncio
import logging
import time
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
    chunk_index: int = 0
    tokens_generated: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


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
    - Async chunk streaming
    - Progress callbacks
    - Cancellation support
    - Error recovery
    - Token counting
    """
    
    def __init__(self, config: StreamConfig = None):
        self.config = config or StreamConfig()
        self._active_streams: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, Callable] = {}
    
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
        
        Args:
            prompt: User prompt
            model: Model name (optional, uses router)
            mode: Generation mode
            on_chunk: Callback for each chunk
            on_progress: Callback for progress (current, total)
            
        Yields:
            StreamChunk: Each chunk of the response
        """
        stream_id = f"{time.time()}"
        start_time = time.time()
        chunk_index = 0
        total_text = ""
        
        try:
            # Get LLM client
            from adapters.llm import OllamaClient
            from services.llm_router import get_llm_router
            
            # Get model from router
            router = get_llm_router()
            route_result = router.route(prompt, mode=mode)
            model = model or route_result["model"]
            
            client = OllamaClient()
            
            # Start streaming
            yield StreamChunk(
                text="",
                status=StreamStatus.STARTING,
                chunk_index=0,
                latency_ms=0
            )
            
            buffer = []
            token_count = 0
            
            for chunk_text in client.stream(prompt, model=model):
                # Check for cancellation
                if stream_id in self._active_streams:
                    task = self._active_streams[stream_id]
                    if task.cancelled():
                        yield StreamChunk(
                            text="",
                            status=StreamStatus.CANCELLED,
                            chunk_index=chunk_index,
                            error="Stream cancelled"
                        )
                        return
                
                # Accumulate buffer
                buffer.append(chunk_text)
                token_count += 1
                
                # Yield when buffer reaches chunk size
                if len(buffer) >= self.config.chunk_size:
                    full_text = "".join(buffer)
                    total_text += full_text
                    
                    chunk = StreamChunk(
                        text=full_text,
                        status=StreamStatus.GENERATING,
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
                    
                    buffer = []
                    chunk_index += 1
                    
                    # Check max tokens
                    if token_count >= self.config.max_tokens:
                        break
            
            # Yield remaining buffer
            if buffer:
                full_text = "".join(buffer)
                total_text += full_text
                
                yield StreamChunk(
                    text=full_text,
                    status=StreamStatus.COMPLETED,
                    chunk_index=chunk_index,
                    tokens_generated=token_count,
                    latency_ms=(time.time() - start_time) * 1000
                )
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield StreamChunk(
                text="",
                status=StreamStatus.ERROR,
                chunk_index=chunk_index,
                error=str(e)
            )
        finally:
            # Cleanup
            if stream_id in self._active_streams:
                del self._active_streams[stream_id]
    
    def cancel_stream(self, stream_id: str) -> bool:
        """Cancel an active stream"""
        if stream_id in self._active_streams:
            self._active_streams[stream_id].cancel()
            return True
        return False
    
    def get_active_count(self) -> int:
        """Get number of active streams"""
        return len(self._active_streams)


# Helper function for sync usage
async def stream_to_string(prompt: str, mode: str = "fast") -> str:
    """Simple helper to get full response from stream"""
    service = StreamingService()
    result = ""
    
    async for chunk in service.stream_generate(prompt, mode=mode):
        if chunk.status in [StreamStatus.GENERATING, StreamStatus.COMPLETED]:
            result += chunk.text
    
    return result


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