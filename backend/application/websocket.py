# controllers/websocket.py - WebSocket Controller
#
# Role: WebSocket connection lifecycle and message handling
# Used by: views/api.py /ws endpoint
# - Connection handling
# - Message parsing and validation
# - Streaming coordination
# - Resume support

import asyncio
import json
import uuid
from typing import Any

from backend.domain.core.logger import get_logger

logger = get_logger(__name__)


class WebSocketController:
    """Controller for WebSocket streaming - handles all WS logic"""

    def __init__(self):
        # sessions: {session_id: {'tasks': []}}
        self.sessions: dict[str, dict] = {}
        # active_requests: {message_id: state}
        self._active_requests: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def handle_connection(self, ws, client_info: str):
        """Handle new WebSocket connection"""
        session_id = f"{client_info}-{len(self.sessions)}"
        self.sessions[session_id] = {"tasks": []}
        logger.info(f"WebSocket connected: {session_id}")
        return session_id

    async def handle_disconnect(self, session_id: str):
        """Handle disconnection — cleans up session state."""
        if session_id in self.sessions:
            del self.sessions[session_id]
        # Prune completed request state on disconnect
        async with self._lock:
            self._prune_completed_requests()
        logger.info(f"WebSocket disconnected: {session_id}")

    async def parse_message(self, data: str) -> dict[str, Any]:
        """Parse incoming WebSocket message"""
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return {"message": data}

    async def validate_request(
        self, msg: dict[str, Any]
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """
        Validate incoming request.
        Returns: (is_valid, error_message, parsed_request)
        """
        task = msg.get("message") or msg.get("prompt") or ""
        model = msg.get("model")
        provider = msg.get("provider")
        message_id = msg.get("message_id") or str(uuid.uuid4())
        last_chunk_index = int(msg.get("last_chunk_index", 0) or 0)
        resume_stream_id = msg.get("resume_stream_id")

        if not model:
            return False, "Model is required", None

        request = {
            "task": task,
            "model": model,
            "provider": provider,
            "message_id": message_id,
            "last_chunk_index": last_chunk_index,
            "resume_stream_id": resume_stream_id,
        }

        return True, None, request

    async def register_request(
        self, message_id: str, model: str, task: str
    ) -> dict[str, Any]:
        """Register or resume a request. Cleans up stale completed requests first."""
        async with self._lock:
            # Prune completed requests to prevent memory leak
            self._prune_completed_requests()

            if message_id not in self._active_requests:
                self._active_requests[message_id] = {
                    "model": model,
                    "task": task,
                    "chunk_index": 0,
                    "is_complete": False,
                }

            return self._active_requests[message_id]

    def _prune_completed_requests(self) -> None:
        """Remove completed requests from tracking (caller must hold _lock)."""
        completed = [
            msg_id
            for msg_id, state in self._active_requests.items()
            if state.get("is_complete", False)
        ]
        for msg_id in completed:
            del self._active_requests[msg_id]
        if completed:
            logger.info(f"[PRUNE] Removed {len(completed)} completed request states")

    async def update_request_state(
        self, message_id: str, chunk_index: int, is_complete: bool = False
    ):
        """Update request state after processing chunk"""
        async with self._lock:
            if message_id in self._active_requests:
                self._active_requests[message_id]["chunk_index"] = chunk_index
                self._active_requests[message_id]["is_complete"] = is_complete

    async def cancel_request(self, message_id: str) -> bool:
        """Cancel a request"""
        async with self._lock:
            if message_id in self._active_requests:
                del self._active_requests[message_id]
                return True
            return False

    async def get_request_state(self, message_id: str) -> dict[str, Any] | None:
        """Get request state for resume"""
        async with self._lock:
            return self._active_requests.get(message_id)

    async def cleanup_completed(self, max_age_seconds: int = 3600):
        """Remove old completed requests"""
        async with self._lock:
            completed = [
                msg_id
                for msg_id, state in self._active_requests.items()
                if state.get("is_complete", False)
            ]
            for msg_id in completed:
                del self._active_requests[msg_id]
            if completed:
                logger.info(f"[CLEANUP] Removed {len(completed)} completed requests")


# Singleton instance
_websocket_controller: WebSocketController | None = None


def get_websocket_controller() -> WebSocketController:
    """Get or create WebSocket controller singleton"""
    global _websocket_controller
    if _websocket_controller is None:
        _websocket_controller = WebSocketController()
    return _websocket_controller
