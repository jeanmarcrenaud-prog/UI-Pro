# views/routers/ws.py - WebSocket endpoint with Unified Streaming Protocol

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional
import json
import uuid
import logging

from models.settings import settings
from backend.infrastructure.streaming_unified import (
    get_unified_streamer,
    WebSocketTransport,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_ws_controller_cached():
    """Get WebSocket controller with caching."""
    from functools import lru_cache

    @lru_cache()
    def get_controller():
        from backend.application.websocket import get_websocket_controller
        return get_controller()

    return get_controller()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time streaming with Unified Protocol."""
    await ws.accept()

    ws_controller = _get_ws_controller_cached()

    client_info = f"{ws.client.host}:{ws.client.port}"
    session_id = await ws_controller.handle_connection(ws, client_info)

    current_message_id: Optional[str] = None

    try:
        while True:
            data = await ws.receive_text()

            # Handle ping
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
                continue

            # Parse request
            try:
                request = await ws_controller.parse_message(data)
            except json.JSONDecodeError:
                request = {"message": data}

            # Handle cancel
            if request.get("type") == "cancel":
                logger.info(f"[ws] Cancel requested for {current_message_id}")
                await ws.send_text(json.dumps({
                    "type": "cancelled",
                    "message_id": current_message_id,
                    "content": ""
                }))
                break

            # Validate request
            is_valid, error_msg, parsed = await ws_controller.validate_request(request)
            if not is_valid:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "message": error_msg,
                    "message_id": request.get("message_id", "unknown")
                }))
                continue

            task = parsed.get("task") or parsed.get("message") or ""
            model = parsed.get("model", "")
            provider = parsed.get("provider", "ollama")
            message_id = parsed.get("message_id", str(uuid.uuid4()))
            max_attempts = parsed.get("max_attempts", 3)

            logger.info(f"[ws] Processing: model='{model}', provider='{provider}', task='{task[:50]}...'")

            current_message_id = message_id

            # Stream using unified protocol
            streamer = get_unified_streamer()
            transport = WebSocketTransport(ws)

            async for event in streamer.stream(
                transport=transport,
                message=task,
                session_id=session_id,
                model=model,
                provider=provider,
                max_attempts=max_attempts,
            ):
                await ws.send_text(event.to_ws())

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        if ws_controller:
            await ws_controller.handle_disconnect(session_id)