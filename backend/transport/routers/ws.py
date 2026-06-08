# views/routers/ws.py - WebSocket endpoint with Unified Streaming Protocol

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.infrastructure.streaming import (
    WebSocketTransport,
    get_unified_streamer,
)

logger = logging.getLogger(__name__)

router = APIRouter()


_ws_controller_cache = None


def _get_ws_controller_cached():
    """Get WebSocket controller with caching."""
    global _ws_controller_cache
    if _ws_controller_cache is None:
        from backend.application.websocket import get_websocket_controller

        _ws_controller_cache = get_websocket_controller()
    return _ws_controller_cache


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time streaming with Unified Protocol."""
    await ws.accept()

    ws_controller = _get_ws_controller_cached()

    client_info = f"{ws.client.host}:{ws.client.port}"
    session_id = await ws_controller.handle_connection(ws, client_info)

    current_message_id: str | None = None

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
                await ws.send_text(
                    json.dumps(
                        {
                            "type": "cancelled",
                            "message_id": current_message_id,
                            "content": "",
                        }
                    )
                )
                break

            # ── Phase 2: human-in-the-loop execution decision ────────
            if request.get("type") == "execute_decision":
                decision = request.get("decision")
                feedback = request.get("feedback")
                msg_id = request.get("message_id", current_message_id or str(uuid.uuid4()))
                logger.info(
                    f"[ws] Execute decision: {decision} "
                    f"(message_id={msg_id}, feedback={feedback})"
                )

                streamer = get_unified_streamer()
                transport = WebSocketTransport(ws)

                async for event in streamer.stream(
                    transport=transport,
                    session_id=session_id,
                    decision=decision,
                    feedback=feedback,
                ):
                    await ws.send_text(event.to_ws())
                continue

            # Validate request
            is_valid, error_msg, parsed = await ws_controller.validate_request(request)
            if not is_valid:
                await ws.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "message": error_msg,
                            "message_id": request.get("message_id", "unknown"),
                        }
                    )
                )
                continue

            task = parsed.get("task") or parsed.get("message") or ""
            model = parsed.get("model", "")
            provider = parsed.get("provider", "ollama")
            message_id = parsed.get("message_id", str(uuid.uuid4()))
            max_attempts = parsed.get("max_attempts", 3)
            resume_from = parsed.get("resume_stream_id")

            # Strip provider prefix from model name (e.g., "ollama-gemma4:e4b" -> "gemma4:e4b")
            if model and provider and model.startswith(f"{provider}-"):
                model = model[len(provider) + 1 :]

            logger.info(
                f"[ws] Processing: model='{model}', provider='{provider}', task='{task[:50]}...'"
            )

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
                resume_from=resume_from,
            ):
                await ws.send_text(event.to_ws())

    except (WebSocketDisconnect, RuntimeError):
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        if ws_controller:
            await ws_controller.handle_disconnect(session_id)
