# api/routers/logs.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.transport.routers.logs instead

from backend.transport.routers.logs import router

__all__ = ["router"]

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