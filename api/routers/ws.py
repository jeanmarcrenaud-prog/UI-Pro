# api/routers/ws.py - WebSocket endpoint with resume support
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any, Optional
import logging
import json
import time
import uuid

from settings import settings

router = APIRouter(tags=["websocket"])

logger = logging.getLogger(__name__)

# ===================== GLOBAL STORES =====================
sessions: Dict[str, Dict[str, Any]] = {}
active_requests: Dict[str, Dict[str, Any]] = {}  # message_id -> state

SESSION_TTL = 3600
MAX_SESSIONS = 1000
API_KEY_HEADER = "x-api-key"


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
        logger.info("Removed oldest session due to MAX_SESSIONS limit")


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """WebSocket endpoint with proper resume support via active_requests"""
    await websocket.accept()

    # API Key check (after accept)
    api_key = getattr(settings, "api_key", None)
    if api_key:
        if websocket.headers.get(API_KEY_HEADER) != api_key:
            await websocket.close(code=1008, reason="Invalid API key")
            return

    client_host = websocket.client.host if websocket.client else "unknown"
    session_id = f"{client_host}-{uuid.uuid4().hex[:8]}"

    # Initialize session
    now = time.time()
    sessions[session_id] = {
        "messages": [],
        "created_at": now,
        "last_activity": now
    }

    from services.streaming import get_streaming_service
    stream_service = get_streaming_service()
    last_cleanup = time.time()
    current_message_id: Optional[str] = None

    logger.info(f"[WS] New connection: {session_id}")

    try:
        while True:
            if time.time() - last_cleanup > 60:
                cleanup_sessions()
                last_cleanup = time.time()

            data = await websocket.receive_text()
            sessions[session_id]["last_activity"] = time.time()

            # Parse incoming message
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                msg = {"message": data}

            # Handle control messages
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "message_id": current_message_id}))
                continue

            if msg.get("type") == "cancel":
                if current_message_id:
                    active_requests.pop(current_message_id, None)
                break

            # Extract request data
            task = msg.get("message") or msg.get("prompt") or ""
            model = msg.get("model")
            provider = msg.get("provider") or "lmstudio"
            message_id = msg.get("message_id") or str(uuid.uuid4())
            last_chunk_index: int = int(msg.get("last_chunk_index", 0) or 0)
            
            print(f"[WS-API] Received: model={model}, provider={provider}, task={task[:50]}...", flush=True)

            current_message_id = message_id

            if not model:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Model is required",
                    "message_id": message_id
                }))
                continue

            # Initialize or get request state for resume
            if message_id not in active_requests:
                active_requests[message_id] = {
                    "model": model,
                    "task": task,
                    "chunk_index": 0,
                    "is_complete": False
                }

            request_state = active_requests[message_id]
            start_chunk = max(last_chunk_index, request_state["chunk_index"])

            # Send resume acknowledgment
            if last_chunk_index > 0:
                await websocket.send_text(json.dumps({
                    "type": "resume_ack",
                    "message_id": message_id,
                    "resuming_from": last_chunk_index,
                    "current_chunk": start_chunk
                }))
                logger.info(f"[WS] Resuming {message_id} from chunk {last_chunk_index}")

            # === Step Flow ===
            await websocket.send_text(json.dumps({
                "type": "step",
                "step_id": "step-analyzing",
                "title": "Analyzing request",
                "status": "done",
                "message_id": message_id,
                "chunk_index": start_chunk
            }))

            await websocket.send_text(json.dumps({
                "type": "step",
                "step_id": "step-planning",
                "title": "Planning solution",
                "status": "active",
                "message_id": message_id,
                "chunk_index": start_chunk
            }))

            # === Token Streaming with Resume Support ===
            chunk_index = start_chunk
            print(f"[WS-API] Starting stream_generate: model={model}, provider={provider}", flush=True)

            try:
                stream_gen = stream_service.stream_generate(task, model=model, provider=provider)
                async for chunk in stream_gen:
                    chunk_text = getattr(chunk, 'text', str(chunk))

                    if chunk_index < last_chunk_index:
                        chunk_index += 1
                        continue

                    chunk_index += 1
                    request_state["chunk_index"] = chunk_index
                    
                    token_count = chunk_index

                    await websocket.send_text(json.dumps({
                        "type": "token",
                        "content": chunk_text,
                        "response": chunk_text,
                        "done": False,
                        "message_id": message_id,
                        "chunk_index": chunk_index,
                        "tokens": token_count
                    }))
            except Exception as stream_err:
                print(f"[WS-API] Stream error: {stream_err}", flush=True)
                logger.error(f"Stream error: {stream_err}", exc_info=True)
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Stream error: {stream_err}",
                    "message_id": message_id
                }))
                break

            # === Complete remaining steps ===
            for step_id, title in [
                ("step-planning", "Planning solution"),
                ("step-executing", "Executing"),
                ("step-reviewing", "Reviewing")
            ]:
                await websocket.send_text(json.dumps({
                    "type": "step",
                    "step_id": step_id,
                    "title": title,
                    "status": "done",
                    "message_id": message_id,
                    "chunk_index": chunk_index
                }))

            # Final done
            await websocket.send_text(json.dumps({
                "type": "done",
                "message_id": message_id,
                "chunk_index": chunk_index,
                "tokens": chunk_index
            }))

            request_state["is_complete"] = True

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Internal server error",
                "message_id": current_message_id
            }))
        except:
            pass
    finally:
        sessions.pop(session_id, None)