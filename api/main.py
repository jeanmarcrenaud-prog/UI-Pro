# api/main.py - FastAPI Application Entry Point
"""
UI-Pro API - FastAPI application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 UI-Pro API starting...")
    yield
    logger.info("👋 UI-Pro API shutting down...")


app = FastAPI(
    title="UI-Pro",
    description="AI Agent Orchestration Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from api.routers import health, chat, execute, ws, logs

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(execute.router)
app.include_router(ws.router)
app.include_router(logs.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)