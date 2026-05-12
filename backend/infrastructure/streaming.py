"""
backend/infrastructure/streaming.py - Streaming Service (LangGraph Version)
Intègre l'OrchestratorAsync basé sur LangGraph pour l'orchestration agentique.
"""

from typing import AsyncIterator, Dict, Any, Optional
import json
import asyncio
import logging
import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from fastapi import WebSocket

logger = logging.getLogger(__name__)


# ====================== Enums & Dataclasses ======================

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
            StreamStatus.STARTING: "step",
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


# ====================== Streaming Service ======================

class StreamingService:
    """Service de streaming qui utilise l'orchestrateur LangGraph."""

    def __init__(self):
        self.orchestrator = None
        self._active_streams: Dict[str, Optional[asyncio.Task]] = {}
        self._stream_counter = 0

    async def _get_orchestrator(self):
        """Lazy loading de l'orchestrateur."""
        if self.orchestrator is None:
            from backend.domain.core.orchestrator_async import get_orchestrator
            self.orchestrator = await get_orchestrator()
        return self.orchestrator

    async def stream_generate(
        self,
        message: str,
        session_id: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        start_chunk: int = 0,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Génère une réponse en streaming via LangGraph.
        Compatible avec WebSocket et SSE.
        """
        self._stream_counter += 1
        stream_id = f"stream-{self._stream_counter}-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        chunk_index = 0

        current = asyncio.current_task()
        self._active_streams[stream_id] = current if current else None

        try:
            orchestrator = await self._get_orchestrator()

            # Step: Analyzing
            yield StreamChunk(
                text="", status=StreamStatus.STARTING, stream_id=stream_id,
                chunk_index=chunk_index, step_id="step-analyzing", step_status="active"
            ).to_dict()
            chunk_index += 1

            # Run orchestrator
            result = await orchestrator.run(
                message=message,
                session_id=session_id,
            )
            # Handle result (dict with status and state)
            if isinstance(result, dict):
                yield self._normalize_event(result, session_id, stream_id, chunk_index, start_time)
                # Check for cancellation
                task = self._active_streams.get(stream_id)
                if task is not None and task.cancelled():
                    raise asyncio.CancelledError()

                # Normalize event for frontend
                normalized = self._normalize_event(event, session_id, stream_id, chunk_index, start_time)
                yield normalized
                chunk_index += 1

                await asyncio.sleep(0.01)  # Yield control

            # Final event
            yield StreamChunk(
                text="", status=StreamStatus.COMPLETED, stream_id=stream_id,
                chunk_index=chunk_index, latency_ms=(time.time() - start_time) * 1000
            ).to_dict()

        except asyncio.CancelledError:
            logger.info(f"Stream {stream_id} was cancelled")
            yield StreamChunk(
                text="", status=StreamStatus.CANCELLED, stream_id=stream_id,
                chunk_index=chunk_index, error="Request cancelled by user"
            ).to_dict()

        except Exception as e:
            logger.exception(f"Unexpected error in streaming, session_id={session_id}")
            yield StreamChunk(
                text="", status=StreamStatus.ERROR, stream_id=stream_id,
                chunk_index=chunk_index, error=str(e)
            ).to_dict()

        finally:
            self._active_streams.pop(stream_id, None)

    def _normalize_event(
        self,
        event: Dict,
        session_id: str,
        stream_id: str,
        chunk_index: int,
        start_time: float
    ) -> Dict[str, Any]:
        """Convertit les événements LangGraph en format attendu par le frontend."""
        # Check for step events
        if isinstance(event, dict):
            if event.get("status") == "failed":
                return StreamChunk(
                    text="", status=StreamStatus.ERROR, stream_id=stream_id,
                    chunk_index=chunk_index, error=event.get("error", "Unknown error"),
                    latency_ms=(time.time() - start_time) * 1000
                ).to_dict()

            # Check for state changes
            state = event.get("state", {})
            if isinstance(state, dict):
                # Analyze step
                if "messages" in state and len(state.get("messages", [])) > 1:
                    return StreamChunk(
                        text="[Analyzing] ", status=StreamStatus.GENERATING, stream_id=stream_id,
                        chunk_index=chunk_index, step_id="step-analyzing", step_status="done",
                        latency_ms=(time.time() - start_time) * 1000
                    ).to_dict()

                # Plan step
                if state.get("plan"):
                    return StreamChunk(
                        text="[Planning] ", status=StreamStatus.GENERATING, stream_id=stream_id,
                        chunk_index=chunk_index, step_id="step-planning", step_status="done",
                        latency_ms=(time.time() - start_time) * 1000
                    ).to_dict()

                # Code step
                if state.get("code"):
                    return StreamChunk(
                        text="[Coding] ", status=StreamStatus.GENERATING, stream_id=stream_id,
                        chunk_index=chunk_index, step_id="step-coding", step_status="done",
                        latency_ms=(time.time() - start_time) * 1000
                    ).to_dict()

                # Review step
                if state.get("review"):
                    review = state.get("review", {})
                    status = "done" if review.get("passed") else "active"
                    return StreamChunk(
                        text="[Reviewing] ", status=StreamStatus.GENERATING, stream_id=stream_id,
                        chunk_index=chunk_index, step_id="step-reviewing", step_status=status,
                        latency_ms=(time.time() - start_time) * 1000
                    ).to_dict()

                # Execution step
                if state.get("execution_result"):
                    result = state.get("execution_result", {})
                    success = result.get("success", False)
                    return StreamChunk(
                        text=f"[Executing] {'Success' if success else 'Failed'}",
                        status=StreamStatus.GENERATING, stream_id=stream_id,
                        chunk_index=chunk_index, step_id="step-executing", step_status="done",
                        latency_ms=(time.time() - start_time) * 1000
                    ).to_dict()

        # Default: token
        return StreamChunk(
            text=str(event)[:100], status=StreamStatus.GENERATING, stream_id=stream_id,
            chunk_index=chunk_index, latency_ms=(time.time() - start_time) * 1000
        ).to_dict()

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
    """Singleton du service de streaming."""
    global _streaming_service
    if _streaming_service is None:
        _streaming_service = StreamingService()
    return _streaming_service


# ====================== WebSocket Helper ======================

async def handle_websocket_stream(ws: WebSocket, message: str, session_id: str):
    """Helper pour gérer un stream WebSocket complet."""
    service = get_streaming_service()

    async for chunk in service.stream_generate(
        message=message,
        session_id=session_id,
    ):
        try:
            await ws.send_text(json.dumps(chunk))
        except Exception:
            logger.warning("WebSocket client disconnected", session_id=session_id)
            break


__all__ = [
    "StreamingService",
    "StreamChunk",
    "StreamStatus",
    "get_streaming_service",
    "handle_websocket_stream",
]