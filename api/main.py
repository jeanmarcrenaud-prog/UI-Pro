# api/main.py - FastAPI Application Entry Point
#
# Role: FastAPI app initialization with modular routers
# Used by: Direct uvicorn run, run.py launcher

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Suppress noise
import logging
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

# Import routers
from api.routers import health, chat, execute, ws, logs

# ===================== FASTAPI APP =====================
app = FastAPI(title="UI Pro - LLM Orchestration Platform")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(execute.router)
app.include_router(ws.router)
app.include_router(logs.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)