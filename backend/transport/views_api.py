# views/api.py - FastAPI Application
#
# Role: Main entry point with app setup, middleware, and core endpoints
# Routers handle: health, status, WebSocket, streaming

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import logging
import time
import json
import traceback
from logging.handlers import RotatingFileHandler
from functools import lru_cache
from typing import Optional, Any, Callable

# ==================== LOGGING ====================

def setup_logging():
    """Configure structured logging."""
    logger = logging.getLogger("api")
    logger.setLevel(logging.INFO)
    
    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(console)
    
    # File handler with rotation
    try:
        file_handler = RotatingFileHandler(
            "logs/api.log",
            maxBytes=5_000_000,
            backupCount=3
        )
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))
        logger.addHandler(file_handler)
    except Exception:
        pass
    
    return logger

logger = setup_logging()


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup/shutdown."""
    logger.info("Starting UI-Pro API...")
    
    # Initialize services
    try:
        from backend.infrastructure.model_discovery import get_model_discovery
        get_model_discovery().discover_all()
        logger.info("Model discovery initialized")
    except Exception as e:
        logger.warning(f"Model discovery init failed: {e}")
    
    # Initialize NVML for GPU monitoring
    try:
        import pynvml
        pynvml.nvmlInit()
        logger.info("NVML initialized for GPU monitoring")
    except Exception:
        logger.info("GPU monitoring not available")
    
    yield
    
    # Shutdown
    try:
        import pynvml
        pynvml.nvmlShutdown()
    except Exception:
        pass
    logger.info("UI-Pro API shutdown complete")


# ==================== APP ====================

app = FastAPI(
    title="UI-Pro API",
    description="AI Agent Orchestration Platform",
    version="1.0.0",
    lifespan=lifespan
)


# ==================== CACHED GETTERS ====================

@lru_cache(maxsize=1)
def _get_settings_cached():
    """Get settings with caching."""
    try:
        from models.settings import settings
        return settings
    except ImportError:
        return None


def _get_setting(attr: str, default: Any = None) -> Any:
    """Get setting attribute safely."""
    settings = _get_settings_cached()
    if settings is None:
        return default
    return getattr(settings, attr, default) or default


# ==================== EXCEPTION HANDLING ==================

class RateLimitExceeded(Exception):
    """Rate limit exception."""
    pass


async def custom_exceptions(request: Request, exc: Exception):
    """Global exception handler."""
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded as SlowAPIRateLimit
    
    if isinstance(exc, SlowAPIRateLimit):
        return await _rate_limit_exceeded_handler(request, exc)
    
    logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# ==================== MIDDLEWARE ====================

app.add_exception_handler(Exception, custom_exceptions)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_observability(request: Request, call_next: Callable):
    """Request logging and tracing middleware."""
    start_time = time.perf_counter()
    request_id = request.headers.get("x-request-id", f"req-{int(time.time() * 1000)}")
    
    logger.info(f"[{request_id}] {request.method} {request.url.path} - started")
    
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"status={response.status_code} duration={duration_ms:.2f}ms"
        )
        
        response.headers["x-request-id"] = request_id
        response.headers["x-duration-ms"] = f"{duration_ms:.2f}"
        
        return response
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"error={type(e).__name__} duration={duration_ms:.2f}ms"
        )
        raise


# ==================== SECURITY ====================

API_KEY_HEADER = "x-api-key"


def verify_api_key(request: Request) -> bool:
    """Verify API key if configured."""
    settings = _get_settings_cached()
    if settings is None:
        return True
    
    api_key = getattr(settings, 'api_key', "")
    
    if not api_key:
        return True
    
    provided_key = request.headers.get(API_KEY_HEADER, "")
    
    if provided_key != api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return True


# ==================== ROUTES ====================

@app.get("/")
def home(request: Request):
    """Home page with API info."""
    model_fast = _get_setting('model_fast', 'N/A')
    model_reasoning = _get_setting('model_reasoning', 'N/A')
    return HTMLResponse(content=f"""
<!DOCTYPE html>
<html>
<head><title>UI Pro</title></head>
<body>
    <h1>UI Pro - LLM Orchestration Platform</h1>
    <p>[START] Agent Orchestration System Ready</p>
    <p>Status: <strong>* Running</strong></p>
    <p>Models: <code>{model_fast}</code> + <code>{model_reasoning}</code></p>
    <p>⚡ Powered by <strong>Ollama</strong> + <strong>FastAPI</strong></p>
    
    <h2>Endpoints</h2>
    <ul>
        <li><code>GET /</code> - This page</li>
        <li><code>GET /health</code> - Health check</li>
        <li><code>GET /status</code> - Status (requires API key)</li>
        <li><code>GET /api/stream</code> - SSE streaming</li>
        <li><code>WebSocket /ws</code> - Real-time streaming</li>
        <li><code>POST /api/chat</code> - REST chat</li>
    </ul>
    
    <p><a href="/docs">📚 API Documentation</a></p>
</body>
</html>
""")


# ==================== IMPORT ROUTERS ====================

from views.routers import health_router, ws_router, stream_router

app.include_router(health_router)
app.include_router(ws_router)
app.include_router(stream_router)


# ==================== CHAT ENDPOINT ====================

class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    provider: Optional[str] = "ollama"


class ChatResponse(BaseModel):
    response: str
    done: bool


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """REST chat endpoint (non-streaming)."""
    from backend.infrastructure.streaming import get_streaming_service
    
    stream_service = get_streaming_service()
    
    full_response = ""
    async for chunk in stream_service.stream_generate(
        prompt=request.message,
        model=request.model or _get_setting('model_fast', 'qwen3.5:0.8b'),
        provider=request.provider or "ollama"
    ):
        if chunk.text:
            full_response += chunk.text
        if chunk.status.value == "completed":
            break
    
    return ChatResponse(response=full_response, done=True)


# ==================== EXECUTE ENDPOINT ====================

class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"


class ExecuteResponse(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None


@app.post("/api/execute", response_model=ExecuteResponse)
async def execute_endpoint(request: ExecuteRequest):
    """Execute code in sandbox."""
    from core.executor import CodeExecutor
    
    executor = CodeExecutor()
    
    try:
        result = await executor.execute_async(
            code=request.code,
            language=request.language
        )
        
        return ExecuteResponse(
            success=result.get("success", False),
            output=result.get("output", ""),
            error=result.get("error")
        )
    except Exception as e:
        return ExecuteResponse(
            success=False,
            output="",
            error=str(e)
        )


# ==================== EXPORTS =====================

__all__ = ["app"]