# views/routers/ws.py - WebSocket endpoint

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.websockets import WebSocketState
from typing import Optional, Dict, Any
import json
import uuid
import logging

from models.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_ws_controller_cached():
    """Get WebSocket controller with caching."""
    from functools import lru_cache
    
    @lru_cache()
    def get_controller():
        from controllers.websocket import get_websocket_controller
        return get_websocket_controller()
    
    return get_controller()


def _get_streaming_service_cached():
    """Get streaming service with caching."""
    from functools import lru_cache
    
    @lru_cache()
    def get_service():
        from backend.infrastructure.streaming import get_streaming_service
        return get_service()
    
    return get_service()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time streaming."""
    await ws.accept()
    
    ws_controller = _get_ws_controller_cached()
    stream_service = _get_streaming_service_cached()
    
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
                continue
            
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
            last_chunk_index = parsed.get("last_chunk_index", 0)
            
            logger.info(f"[ws] Processing: model='{model}', provider='{provider}', task='{task[:50]}...'")
            
            current_message_id = message_id
            request_state = await ws_controller.register_request(message_id, model, task)
            start_chunk = max(last_chunk_index, request_state["chunk_index"])
            
            # Resume acknowledgment
            if last_chunk_index > 0:
                await ws.send_text(json.dumps({
                    "type": "resume_ack",
                    "message_id": message_id,
                    "resuming_from": last_chunk_index,
                    "current_chunk": start_chunk
                }))
            
            # Stream
            async for chunk in stream_service.stream_generate(
                task,
                model=model,
                provider=provider,
                start_chunk=start_chunk
            ):
                # Handle completion
                if chunk.status.value == "completed":
                    await ws.send_text(json.dumps({
                        "type": "done",
                        "message_id": message_id,
                        "chunk_index": chunk.chunk_index
                    }))
                    for step_id, title in [
                        ("step-planning", "Planning solution"),
                        ("step-executing", "Executing"),
                        ("step-reviewing", "Reviewing")
                    ]:
                        await ws.send_text(json.dumps({
                            "type": "step",
                            "step_id": step_id,
                            "title": title,
                            "status": "done",
                            "message_id": message_id,
                            "chunk_index": chunk.chunk_index
                        }))
                    await ws_controller.update_request_state(message_id, chunk.chunk_index, is_complete=True)
                    continue
                
                # Handle errors
                if chunk.status.value == "error":
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": chunk.error or "Generation error",
                        "message_id": message_id,
                        "chunk_index": chunk.chunk_index
                    }))
                    await ws_controller.update_request_state(message_id, chunk.chunk_index, is_complete=True)
                    continue
                
                # Handle cancellation
                if chunk.status.value == "cancelled":
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Request cancelled by user",
                        "message_id": message_id,
                        "chunk_index": chunk.chunk_index
                    }))
                    await ws_controller.update_request_state(message_id, chunk.chunk_index, is_complete=True)
                    continue
                
                # Handle step events
                if chunk.step_id:
                    await ws.send_text(json.dumps({
                        "type": "step",
                        "step_id": chunk.step_id,
                        "title": chunk.step_id.replace("step-", "").replace("-", " ").title(),
                        "status": chunk.step_status,
                        "message_id": message_id,
                        "chunk_index": chunk.chunk_index
                    }))
                    await ws_controller.update_request_state(message_id, chunk.chunk_index)
                    continue
                
                # Handle token chunks
                if chunk.text:
                    await ws_controller.update_request_state(message_id, chunk.chunk_index)
                    await ws.send_text(json.dumps({
                        "type": "token",
                        "content": chunk.text,
                        "response": chunk.text,
                        "done": False,
                        "message_id": message_id,
                        "chunk_index": chunk.chunk_index,
                        "tokens_generated": chunk.tokens_generated or 0
                    }))
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        if ws_controller:
            await ws_controller.handle_disconnect(session_id)
        if ws.client and hasattr(ws.client, 'state'):
            try:
                if ws.client.state != WebSocketState.DISCONNECTED:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Connection closed",
                        "message_id": current_message_id
                    }))
            except Exception:
                pass