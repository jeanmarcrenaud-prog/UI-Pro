"""
⚠️ DEPRECATED — All functionality migrated to backend/infrastructure/streaming/ package.

Import from `backend.infrastructure.streaming` instead.
"""

import warnings

from backend.infrastructure.streaming import (  # noqa: F401
    CHUNK_THRESHOLD,
    SSETransport,
    StreamChunk,
    StreamEvent,
    StreamStatus,
    StreamTransport,
    UnifiedStreamer,
    WebSocketTransport,
    _TokenBuffer,
    create_sse_response,
    get_unified_streamer,
    parse_event,
    stream_chat,
)

warnings.warn(
    "streaming_unified is deprecated. Use backend.infrastructure.streaming instead.",
    DeprecationWarning,
    stacklevel=2,
)
