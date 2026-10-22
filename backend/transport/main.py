#QR|# api/main.py - FastAPI Application Entry Point
#YW|"""
#SQ|UI-Pro API - FastAPI application entry point
#NR|"""
#BT|
#HM|import logging
from contextlib import asynccontextmanager
#XW|
from fastapi import FastAPI
#HH|from fastapi.middleware.cors import CORSMiddleware

from backend.transport.routers import chat, execute, health, logs, templates, ws, mcp
from backend.transport.routers.hermes import router as hermes_router
from backend.transport.routers.mario import router as mario_router

#JW|logger = logging.getLogger("api")
#HX|
#KS|
#PP|@asynccontextmanager
#QZ|async def lifespan(app: FastAPI):
#PJ|    logger.info("[START] UI-Pro API starting...")
#ZP|
#WZ|    # Warm up the LangGraph orchestrator (and its SQLite checkpointer) as
#YT|    # part of the app lifecycle instead of lazily on the first request:
#XN|    # the first chat message doesn't pay the one-time init cost and the
#BS|    # checkpointer lifecycle is owned by the application, not the first call.
#PN|    try:
#BT|        from backend.domain.core.langgraph import get_orchestrator
#ZR|
#QM|        await get_orchestrator()
#BN|        logger.info("[START] LangGraph orchestrator ready")
#RK|    except Exception:
#BV|        logger.exception("[START] Orchestrator warm-up failed — will retry on first request")
#WV|
#RN|    yield
#YB|    logger.info("[STOP] UI-Pro API shutting down...")
#PN|    try:
#MY|        from backend.domain.core.langgraph.checkpointer import close_checkpointer
#MS|
#SB|        await close_checkpointer()
#RK|    except Exception:
#VK|        logger.exception("[STOP] Checkpointer close failed")
#PN|    try:
#BH|        from backend.infrastructure.llm.hermes_acp import close_acp_pool
#KT|
#JH|        await close_acp_pool()
#RK|    except Exception:
#KV|        logger.exception("[STOP] ACP pool close failed")
#BN|
#QW|
app = FastAPI(
    title="UI-Pro",
    description="AI Agent Orchestration Platform",
    version="1.0.0",
)
#WH|
#KR|from backend.domain.settings import get_settings
#QH|
#YH|_cors_origins = get_settings().cors_origins
#HB|logger.info(f"CORS origins: {_cors_origins}")
#RJ|
#TY|app.add_middleware(
#MY|    CORSMiddleware,
#QQ|    allow_origins=_cors_origins,
#SK|    allow_origin_regex=r"https?://localhost(:\d+)?",
#ZQ|    allow_credentials=True,
#RP|    allow_methods=["*"],
#ZV|    allow_headers=["*"],
#SZ|)
#PR|
#ZN|# Add rate limiting middleware (controlled via settings.rate_limit_enabled).
#VK|# The rate_limit module is an optional dependency. We only catch ImportError
#NB|# on THAT specific import — other code (settings, middleware instantiation)
#NQ|# must fail loud so we don't silently disable rate limiting on a real bug.
#BJ|try:
#HY|    from backend.infrastructure.rate_limit import (
#XR|        RateLimitConfig,
#KN|        RateLimitMiddleware,
#JP|    )
#YT|    _rate_limit_available = True
#ZH|except ImportError as e:
#YX|    logger.warning(f"Rate limiting not available: {e}")
#QZ|    _rate_limit_available = False
#SR|
#TY|if _rate_limit_available:
#BP|    settings = get_settings()
#MT|    if settings.rate_limit_enabled:
#JJ|        app.add_middleware(
#VJ|            RateLimitMiddleware,
#PS|            config=RateLimitConfig(
#ZH|                requests_per_minute=settings.rate_limit_requests_per_minute,
#SX|                requests_per_hour=settings.rate_limit_requests_per_hour,
#VV|                burst_size=settings.rate_limit_burst_size,
#MR|            ),
#BJ|        )
#XB|        logger.info(
#PW|            f"Rate limiting enabled "
#PX|            f"({settings.rate_limit_requests_per_hour}/h, "
#YT|            f"{settings.rate_limit_requests_per_minute}/min, "
#KT|            f"burst={settings.rate_limit_burst_size})"
#VB|        )
#ZZ|    else:
#VJ|        logger.info("Rate limiting disabled via settings")
#VS|
#HT|
#TS|
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(execute.router)
app.include_router(ws.router)
app.include_router(logs.router)
app.include_router(mario_router)
app.include_router(mcp.router)
app.include_router(hermes_router)
app.include_router(templates.router)
#BK|
#BQ|
#XN|if __name__ == "__main__":
#WN|    import uvicorn
#XM|
#JV|    uvicorn.run("backend.transport.main:app", host="0.0.0.0", port=8000, reload=True)