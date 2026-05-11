# services/streaming.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.infrastructure.streaming instead

from backend.infrastructure.streaming import (
    StreamingService,
    StreamChunk,
    StreamConfig,
    StreamStatus,
    get_streaming_service,
)

__all__ = [
    "StreamingService",
    "StreamChunk",
    "StreamConfig",
    "StreamStatus",
    "get_streaming_service",
]