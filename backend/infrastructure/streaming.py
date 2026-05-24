"""
backend/infrastructure/streaming.py - Streaming Service (LangGraph Version)

⚠️  DEPRECATED — All functionality migrated to streaming_unified.py.
    Import from `backend.infrastructure.streaming_unified` instead.
    This shim will be removed in a future version.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "backend.infrastructure.streaming is deprecated. "
    "Use backend.infrastructure.streaming_unified instead.",
    DeprecationWarning,
    stacklevel=2,
)

from fastapi.responses import StreamingResponse  # noqa: F401

from backend.infrastructure.streaming_unified import (
    SSETransport,
    StreamChunk,
    StreamEvent,
    StreamStatus,
    StreamTransport,
    UnifiedStreamer,
    WebSocketTransport,
    create_sse_response,
    get_unified_streamer,
    stream_chat,
)

__all__ = [
    "SSETransport",
    "StreamChunk",
    "StreamEvent",
    "StreamStatus",
    "StreamTransport",
    "StreamingResponse",
    "UnifiedStreamer",
    "WebSocketTransport",
    "create_sse_response",
    "get_unified_streamer",
    "stream_chat",
]
