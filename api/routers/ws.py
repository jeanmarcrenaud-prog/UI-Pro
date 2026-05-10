# api/routers/ws.py - WebSocket endpoint (delegates to controller)
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import json
import time

from settings import settings

router = APIRouter(tags=["websocket"])

logger = logging.getLogger(__name__)

API_KEY_HEADER = "x-api-key"

# Session management
sessions = {}
SESSION_TTL = 3600
MAX_SESSIONS = 1000


def cleanup_sessions():
    """Remove expired and excess sessions"""
    now = time.time()
    expired = [sid for sid, data in sessions.items()
             if now - data.get("last_activity", 0) > SESSION_TTL]
    for sid in expired:
        sessions.pop(sid, None)
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired sessions")
    if len(sessions) >= MAX_SESSIONS:
        oldest_sid = min(sessions.keys(), key=lambda k: sessions[k].get("last_activity", 0))
        sessions.pop(oldest_sid, None)


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """WebSocket endpoint - delegates to WebSocketController"""
    await websocket.accept()

    # API Key check
    api_key = getattr(settings, "api_key", None)
    if api_key:
        if websocket.headers.get(API_KEY_HEADER) != api_key:
            await websocket.close(code=1008, reason="Invalid API key")
            return

    client_host = websocket.client.host if websocket.client else "unknown"
    session_id = f"{client_host}-{time.time()}"
    sessions[session_id] = {"messages": [], "created_at": time.time(), "last_activity": time.time()}

    # Get controller
    from controllers.websocket import get_websocket_controller
    controller = get_websocket_controller()

    from services.streaming import get_streaming_service
    stream_service = get_streaming_service()

    last_cleanup = time.time()
    current_message_id = None

    logger.info(f"[WS] New connection: {session_id}")

    try:
        while True:
            if time.time() - last_cleanup > 60:
                cleanup_sessions()
                last_cleanup = time.time()

            data = await websocket.receive_text()
            sessions[session_id]["last_activity"] = time.time()

            # Parse message
            msg = await controller.parse_message(data)

            # Handle control messages
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "message_id": current_message_id}))
                continue

            if msg.get("type") == "cancel":
                if current_message_id:
                    await controller.cancel_request(current_message_id)
                break

            # Validate request
            is_valid, error, request = await controller.validate_request(msg)
            if not is_valid:
                await websocket.send_text(json.dumps({"type": "error", "message": error, "message_id": request.get("message_id")}))
                continue

            current_message_id = request["message_id"]

            # Register request for resume
            request_state = await controller.register_request(
                request["message_id"], request["model"], request["task"]
            )
            start_chunk = max(request["last_chunk_index"], request_state["chunk_index"])

            # Resume acknowledgment
            if request["last_chunk_index"] > 0:
                await websocket.send_text(json.dumps({
                    "type": "resume_ack",
                    "message_id": request["message_id"],
                    "resuming_from": request["last_chunk_index"],
                    "current_chunk": start_chunk
                }))

            # Step: analyzing
            await websocket.send_text(json.dumps({
                "type": "step", "step_id": "step-analyzing", "title": "Analyzing request",
                "status": "done", "message_id": request["message_id"], "chunk_index": start_chunk
            }))

            # Step: planning
            await websocket.send_text(json.dumps({
                "type": "step", "step_id": "step-planning", "title": "Planning solution",
                "status": "active", "message_id": request["message_id"], "chunk_index": start_chunk
            }))

            # Stream tokens
            chunk_index = start_chunk
            token_count = 0
            try:
                stream_gen = stream_service.stream_generate(request["task"], model=request["model"], provider=request["provider"])
                async for chunk in stream_gen:
                    chunk_text = getattr(chunk, 'text', str(chunk))
                    token_count = getattr(chunk, 'tokens_generated', chunk_index) or chunk_index
                    if chunk_index < request["last_chunk_index"]:
                        chunk_index += 1
                        continue
                    chunk_index += 1
                    await controller.update_request_state(request["message_id"], chunk_index)
                    await websocket.send_text(json.dumps({
                        "type": "token", "content": chunk_text, "response": chunk_text,
                        "done": False, "message_id": request["message_id"],
                        "chunk_index": chunk_index, "tokens": token_count
                    }))
            except Exception as e:
                logger.error(f"Stream error: {e}")
                await websocket.send_text(json.dumps({"type": "error", "message": str(e), "message_id": request["message_id"]}))
                break

            # Complete steps
            for step_id, title in [("step-planning", "Planning solution"), ("step-executing", "Executing"), ("step-reviewing", "Reviewing")]:
                await websocket.send_text(json.dumps({
                    "type": "step", "step_id": step_id, "title": title,
                    "status": "done", "message_id": request["message_id"], "chunk_index": chunk_index
                }))

            await websocket.send_text(json.dumps({
                "type": "done", "message_id": request["message_id"], "chunk_index": chunk_index, "tokens": token_count
            }))
            await controller.update_request_state(request["message_id"], chunk_index, is_complete=True)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        sessions.pop(session_id, None)