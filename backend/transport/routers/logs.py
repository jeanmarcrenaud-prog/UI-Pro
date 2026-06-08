# api/routers/logs.py - Log management and streaming
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket
from pydantic import BaseModel

router = APIRouter(tags=["logs"], prefix="/api")

logger = logging.getLogger(__name__)

_log_subscriptions: set = set()

# Log levels available
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

LOGS_DIR = Path("logs")

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)


class LogLevelRequest(BaseModel):
    level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL


class LogLevelResponse(BaseModel):
    current_level: str
    available_levels: list[str]
    timestamp: str


class LogFileInfo(BaseModel):
    name: str
    size_bytes: int
    modified: str
    level: str


class LogsStatusResponse(BaseModel):
    enabled: bool
    directory: str
    current_level: str
    files: list[LogFileInfo]
    total_size_mb: float


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


@router.get("/logs/status", response_model=LogsStatusResponse)
async def get_logs_status():
    """Get current logging status and configuration"""
    try:
        root_logger = logging.getLogger()
        current_level = logging.getLevelName(root_logger.level)

        # Get log files
        log_files: list[LogFileInfo] = []
        total_size = 0

        if LOGS_DIR.exists():
            for log_file in sorted(
                LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True
            ):
                size = log_file.stat().st_size
                total_size += size
                modified = datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()

                log_files.append(
                    LogFileInfo(
                        name=log_file.name,
                        size_bytes=size,
                        modified=modified,
                        level="JSON",  # Our files are JSON formatted
                    )
                )

        return LogsStatusResponse(
            enabled=True,
            directory=str(LOGS_DIR.absolute()),
            current_level=current_level,
            files=log_files[:10],  # Last 10 files
            total_size_mb=round(total_size / (1024 * 1024), 2),
        )
    except Exception as e:
        logger.error(f"Failed to get logs status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/level", response_model=LogLevelResponse)
async def get_log_level():
    """Get current log level"""
    try:
        root_logger = logging.getLogger()
        level_name = logging.getLevelName(root_logger.level)

        logger.debug(f"[LOGS] Returning current level: {level_name}")

        return LogLevelResponse(
            current_level=level_name,
            available_levels=list(LOG_LEVELS.keys()),
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.error(f"[LOGS] Failed to get log level: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs/level", response_model=LogLevelResponse)
async def set_log_level(request: LogLevelRequest):
    """Set log level for all loggers"""
    if request.level.upper() not in LOG_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid log level. Must be one of: {', '.join(LOG_LEVELS.keys())}",
        )

    try:
        level_str = request.level.upper()
        level = LOG_LEVELS[level_str]

        # Set level on root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        logger.info(f"[LOGS] Set root logger level to {level_str}")

        # Set level on all existing loggers
        for name in logging.Logger.manager.loggerDict:
            logger_obj = logging.getLogger(name)
            logger_obj.setLevel(level)

        # Persist to settings
        try:
            from backend.domain.settings import settings

            settings.set_log_level(level_str)
            logger.info(f"[LOGS] Persisted log level {level_str} to settings")
        except Exception as import_err:
            logger.warning(f"[LOGS] Could not persist to settings: {import_err}")
            # Still return success - in-memory change worked

        return LogLevelResponse(
            current_level=level_str,
            available_levels=list(LOG_LEVELS.keys()),
            timestamp=datetime.now().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LOGS] Failed to set log level: {type(e).__name__}: {e!s}")
        raise HTTPException(status_code=500, detail=f"Failed to set log level: {e!s}")


@router.get("/logs/files/{filename}")
async def get_log_file(filename: str):
    """Download a specific log file"""

    # Prevent directory traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = LOGS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    return {
        "filename": filename,
        "size_bytes": file_path.stat().st_size,
        "content": file_path.read_text()[:10000],  # First 10KB
    }


# Helper to emit to log subscribers (used by other modules)
async def emit_to_log_subscribers(message: str):
    """Emit a log message to all subscribed WebSocket clients"""
    for log_ws in list(_log_subscriptions):
        try:
            await log_ws.send_text(
                json.dumps(
                    {
                        "type": "log",
                        "message": message[:100] if message else "",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )
        except Exception as e:
            logger.warning(f"Log subscription error: {e}")
