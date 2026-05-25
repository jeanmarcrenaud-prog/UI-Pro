"""
Unified Streaming Protocol — models, parser, transports, streamer, legacy API.
"""

from backend.infrastructure.streaming.legacy import (
    UnifiedStreamer,
    create_sse_response,
    get_unified_streamer,
    stream_chat,
)
from backend.infrastructure.streaming.models import (
    CHUNK_THRESHOLD,
    StreamChunk,
    StreamEvent,
    StreamStatus,
    _TokenBuffer,
)
from backend.infrastructure.streaming.parser import parse_event
from backend.infrastructure.streaming.transports import (
    SSETransport,
    StreamTransport,
    WebSocketTransport,
)

__all__ = [
    "CHUNK_THRESHOLD",
    "SSETransport",
    "StreamChunk",
    "StreamEvent",
    "StreamStatus",
    "StreamTransport",
    "UnifiedStreamer",
    "WebSocketTransport",
    "_TokenBuffer",
    "create_sse_response",
    "get_unified_streamer",
    "parse_event",
    "stream_chat",
]
