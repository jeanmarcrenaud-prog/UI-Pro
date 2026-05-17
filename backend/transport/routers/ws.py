# views/routers/ws.py - WebSocket endpoint with LangGraph Streaming

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
        from backend.application.websocket import get_websocket_controller
        return get_websocket_controller()

    return get_controller()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time streaming with LangGraph."""
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
            max_attempts = parsed.get("max_attempts", 3)

            logger.info(f"[ws] Processing: model='{model}', provider='{provider}', task='{task[:50]}...'")

            current_message_id = message_id

            # Stream using new LangGraph orchestrator with user-selected model
            async for event in _stream_with_langgraph(task, session_id, max_attempts, ws_controller, message_id, model, provider):
                await ws.send_text(json.dumps(event))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        if ws_controller:
            await ws_controller.handle_disconnect(session_id)


async def _stream_with_langgraph(task: str, session_id: str, max_attempts: int, ws_controller, message_id: str, model: str = "", provider: str = "ollama"):
    """Stream using LangGraph orchestrator with proper event formatting and user-selected model."""
    try:
        # Import here to avoid circular imports
        from backend.domain.core.langgraph import stream_agent as langgraph_stream

        logger.info(f"[stream] Starting langgraph stream for task: {task[:50]}...")

        event_count = 0
        accumulated_content = ""  # Track for token counting

        async for event in langgraph_stream(
            message=task,
            session_id=session_id,
            max_attempts=max_attempts,
            model=model,  # Pass user-selected model
            provider=provider  # Pass user-selected provider
        ):
            # Map backend phases to frontend step IDs
            PHASE_MAP = {
                "orchestrator": "analyzing",
                "planning": "planning",
                "coding": "executing",
                "reviewing": "reviewing",
                "executing": "executing",
                "completed": "completed",
            }

            # Parse stream_agent events
            if isinstance(event, str):
                event_count += 1
                logger.info(f"[stream] Event {event_count}: {event[:80]}...")

                if event.startswith("[STEP]"):
                    # Format: [STEP]phase:message
                    parts = event[6:].split(":", 1)
                    phase = parts[0] if parts else "step"
                    msg = parts[1] if len(parts) > 1 else ""

                    # Map phase to frontend step ID
                    step_id = f"step-{PHASE_MAP.get(phase, phase)}"

                    yield {
                        "type": "step",
                        "step_id": step_id,
                        "title": phase.replace("_", " ").title(),
                        "status": "active",
                        "message_id": message_id,
                        "content": msg
                    }

                elif event.startswith("[TOKEN]"):
                    # Format: [TOKEN]content
                    content = event[7:]
                    accumulated_content += content

                    # Calculate token count (rough: 1 token ≈ 2 chars for LLM output)
                    # Better: integrate tiktoken if performance needed
                    token_count = max(1, len(accumulated_content) // 2)

                    yield {
                        "type": "token",
                        "content": content,
                        "response": content,
                        "done": False,
                        "message_id": message_id,
                        "token_count": token_count,  # 👈 Real token count
                    }

                elif event.startswith("[TOOL]"):
                    # Format: [TOOL]action:message
                    parts = event[6:].split(":", 1)
                    action = parts[0] if parts else "tool"
                    msg = parts[1] if len(parts) > 1 else ""

                    yield {
                        "type": "step",
                        "step_id": f"tool-{action}",
                        "title": action.replace("_", " ").title(),
                        "status": "done",
                        "message_id": message_id,
                        "content": msg
                    }

                elif event.startswith("[ERROR]"):
                    # Format: [ERROR]code:message
                    parts = event[7:].split(":", 1)
                    code = parts[0] if parts else "500"
                    msg = parts[1] if len(parts) > 1 else ""

                    yield {
                        "type": "error",
                        "message": msg,
                        "code": code,
                        "message_id": message_id,
                    }

                elif event == "[DONE]":
                    yield {
                        "type": "done",
                        "message_id": message_id,
                    }

            else:
                # Dict event fallback
                yield event

    except Exception as e:
        logger.error(f"LangGraph streaming error: {e}")
        yield {
            "type": "error",
            "message": str(e),
            "message_id": message_id,
        }
