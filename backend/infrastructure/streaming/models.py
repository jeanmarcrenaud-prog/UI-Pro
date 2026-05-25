"""
Streaming models: StreamStatus, StreamEvent, StreamChunk, _TokenBuffer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

CHUNK_THRESHOLD = 20  # chars ~5 tokens before yielding a token event


class StreamStatus(Enum):
    STARTING = "starting"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class StreamEvent:
    """Unified stream event format for both SSE and WebSocket."""

    event_type: str
    status: StreamStatus = StreamStatus.GENERATING
    stream_id: str = ""
    message_id: str = ""
    content: str = ""
    step_id: str | None = None
    title: str | None = None
    done: bool = False
    error: str | None = None
    code: str | None = None
    token_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    _SERIALIZERS: ClassVar[dict[str, dict[str, Any]]] = {
        "stream_id": {},
        "step": {
            "step_id": lambda e: e.step_id or "step-unknown",
            "title": lambda e: e.title or "Step",
            "status": lambda e: "active" if e.status == StreamStatus.GENERATING else "done",
            "content": lambda e: e.content,
        },
        "token": {
            "content": lambda e: e.content,
            "response": lambda e: e.content,
            "done": lambda e: e.done,
            "token_count": lambda e: e.token_count,
        },
        "tool": {
            "step_id": lambda e: e.step_id or "tool-unknown",
            "title": lambda e: e.title or "Tool",
            "status": lambda e: "done",
            "content": lambda e: e.content,
        },
        "error": {
            "message": lambda e: e.content,
            "code": lambda e: e.code or "500",
        },
        "done": {"done": lambda e: True},
        "resumed": {"from_index": lambda e: 0},
    }

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.event_type,
            "message_id": self.message_id,
            "stream_id": self.stream_id,
            "timestamp": self.timestamp.isoformat(),
        }
        serializer = self._SERIALIZERS.get(self.event_type)
        if serializer:
            for key, extractor in serializer.items():
                result[key] = extractor(self)
        return result

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.to_dict())}\n\n"

    def to_ws(self) -> str:
        return json.dumps(self.to_dict())


class _TokenBuffer:
    """Accumulates tokens and flushes in chunks or on demand."""

    def __init__(self, chunk_threshold: int = CHUNK_THRESHOLD):
        self._buffer = ""
        self._total = 0
        self._threshold = chunk_threshold

    def append(self, content: str) -> None:
        self._buffer += content
        self._total += len(content)

    @property
    def size(self) -> int:
        return len(self._buffer)

    @property
    def total(self) -> int:
        return self._total

    @property
    def is_ready(self) -> bool:
        return self.size >= self._threshold

    @property
    def is_empty(self) -> bool:
        return self.size == 0

    def flush(self) -> StreamEvent | None:
        if self.is_empty:
            return None
        event = self._build_event()
        self._buffer = ""
        return event

    def drain(self) -> StreamEvent | None:
        return self.flush()

    def _build_event(self) -> StreamEvent:
        return StreamEvent(
            event_type="token",
            content=self._buffer,
            done=False,
            token_count=max(1, self._total // 2),
        )


@dataclass(slots=True)
class StreamChunk:
    """Backward-compatible StreamChunk for legacy stream_chat consumers.

    Deprecated: Use StreamEvent directly in new code.
    """

    text: str
    status: StreamStatus
    stream_id: str
    chunk_index: int
    tokens_generated: int = 0
    latency_ms: float = 0.0
    error: str | None = None


__all__ = [
    "CHUNK_THRESHOLD",
    "StreamChunk",
    "StreamEvent",
    "StreamStatus",
    "_TokenBuffer",
]
