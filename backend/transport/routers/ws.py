# views/routers/ws.py - WebSocket endpoint with Unified Streaming Protocol

import asyncio
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
    stream_task: asyncio.Task | None = None
    cancel_requested = False

    async def run_stream(streamer, transport, **kwargs):
        """Consume the unified streamer and forward events to the client.

        Runs as a background task so the receive loop stays responsive
        (ping / cancel can arrive during generation).
        """
        async for event in streamer.stream(transport=transport, **kwargs):
            if cancel_requested:
                # Suppress trailing events (e.g. the CancelledError fallback
                # event) after the client asked to stop.
                continue
            await ws.send_text(event.to_ws())

    async def stop_inflight() -> None:
        """Cancel any running stream and reset the cancel flag."""
        nonlocal stream_task, cancel_requested
        if stream_task and not stream_task.done():
            cancel_requested = True
            stream_task.cancel()
            await asyncio.gather(stream_task, return_exceptions=True)
        stream_task = None
        cancel_requested = False

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

            # Handle cancel — stop the in-flight stream (if any).
            # The stream runs as a background task so this receive loop
            # stays responsive during generation.
            if request.get("type") == "cancel":
                if stream_task and not stream_task.done():
                    logger.info(f"[ws] Cancelling stream for {current_message_id}")
                    cancel_requested = True
                    stream_task.cancel()
                    await asyncio.gather(stream_task, return_exceptions=True)
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

            # Stop any previous in-flight stream (defensive; the client serializes)
            await stop_inflight()

            # Stream using unified protocol (background task so cancel works mid-stream)
            streamer = get_unified_streamer()
            transport = WebSocketTransport(ws)
            stream_task = asyncio.create_task(
                run_stream(
                    streamer,
                    transport,
                    message=task,
                    session_id=session_id,
                    model=model,
                    provider=provider,
                    max_attempts=max_attempts,
                    resume_from=resume_from,
                )
            )

    except (WebSocketDisconnect, RuntimeError):
        logger.info(f"WebSocket disconnected: {session_id}")
        # Stop any in-flight stream when the client goes away
        await stop_inflight()
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        if ws_controller:
            await ws_controller.handle_disconnect(session_id)
