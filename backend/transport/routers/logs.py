# api/routers/logs.py - Log streaming WebSocket
from fastapi import APIRouter, WebSocket
import logging
import asyncio

router = APIRouter(tags=["logs"])

logger = logging.getLogger(__name__)

_log_subscriptions: set = set()


@router.websocket("/logs")
async def ws_logs(websocket: WebSocket):
    """WebSocket endpoint for streaming backend logs"""
    await websocket.accept()

    # Add to subscriptions
    _log_subscriptions.add(websocket)

    logger.info("[WS LOGS] Client connected")

    try:
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"[WS LOGS] Error: {e}")
    finally:
        _log_subscriptions.discard(websocket)
        logger.info("[WS LOGS] Client disconnected")


# Helper to emit to log subscribers (used by other modules)
async def emit_to_log_subscribers(message: str):
    """Emit a log message to all subscribed WebSocket clients"""
    for log_ws in list(_log_subscriptions):
        try:
            await log_ws.send_text(json.dumps({
                "type": "log",
                "message": message[:100] if message else "",
            }))
        except Exception as e:
            logger.warning(f"Log subscription error: {e}")


import json