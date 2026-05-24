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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware (enabled by default, disable via RATE_LIMIT_ENABLED=false)
try:
    import os

    from backend.infrastructure.rate_limit import RateLimitConfig, RateLimitMiddleware

    if os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false":
        app.add_middleware(
            RateLimitMiddleware,
            config=RateLimitConfig(
                requests_per_minute=60, requests_per_hour=1000, burst_size=10
            ),
        )
        logger.info("Rate limiting enabled")
    else:
        logger.info("Rate limiting disabled via RATE_LIMIT_ENABLED=false")
except ImportError:
    logger.warning("Rate limiting not available")


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
