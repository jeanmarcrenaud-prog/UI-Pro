# api/main.py - FastAPI Application Entry Point
"""
UI-Pro API - FastAPI application entry point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[START] UI-Pro API starting...")
    yield
    logger.info("[STOP] UI-Pro API shutting down...")


app = FastAPI(
    title="UI-Pro",
    description="AI Agent Orchestration Platform",
    version="1.0.0",
    lifespan=lifespan,
)

from backend.domain.settings import get_settings

_cors_origins = get_settings().cors_origins
logger.info(f"CORS origins: {_cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https?://localhost(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware (controlled via settings.rate_limit_enabled).
# The rate_limit module is an optional dependency. We only catch ImportError
# on THAT specific import — other code (settings, middleware instantiation)
# must fail loud so we don't silently disable rate limiting on a real bug.
try:
    from backend.infrastructure.rate_limit import (
        RateLimitConfig,
        RateLimitMiddleware,
    )
    _rate_limit_available = True
except ImportError as e:
    logger.warning(f"Rate limiting not available: {e}")
    _rate_limit_available = False

if _rate_limit_available:
    settings = get_settings()
    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            config=RateLimitConfig(
                requests_per_minute=settings.rate_limit_requests_per_minute,
                requests_per_hour=settings.rate_limit_requests_per_hour,
                burst_size=settings.rate_limit_burst_size,
            ),
        )
        logger.info(
            f"Rate limiting enabled "
            f"({settings.rate_limit_requests_per_hour}/h, "
            f"{settings.rate_limit_requests_per_minute}/min, "
            f"burst={settings.rate_limit_burst_size})"
        )
    else:
        logger.info("Rate limiting disabled via settings")


# Include routers
from backend.transport.routers import chat, execute, health, logs, ws

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(execute.router)
app.include_router(ws.router)
app.include_router(logs.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
