from fastapi import FastAPI, WebSocket, Request, HTTPException, Depends
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import logging
import time
import json
import sys
from typing import Callable, Dict, Any, Optional
import traceback
from logging.handlers import RotatingFileHandler
import threading

# Suppress noise
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)


# == Structured Logging Configuration ==
class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logs"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(log_data, default=str)


# Configure logging
log_dir = "logs"
import os

os.makedirs(log_dir, exist_ok=True)
file_handler = RotatingFileHandler(
    f"{log_dir}/app.log",
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5
)
file_handler.setFormatter(JSONFormatter())
file_handler.setLevel(logging.INFO)

# Console handler for development
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(JSONFormatter())
console_handler.setLevel(logging.WARNING)

# Get root logger and configure
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)


# ==================== THREAD-SAFE STATE MANAGEMENT ====================

class ThreadSafeStore:
    """Thread-safe storage for errors and sessions"""
    
    def __init__(self, max_size: int = 100):
        self._errors: list[Dict[str, Any]] = []
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._lock = threading.RLock()
    
    @property
    def errors(self) -> list[Dict[str, Any]]:
        with self._lock:
            return self._errors
    
    def add_error(self, error: Dict[str, Any]) -> None:
        with self._lock:
            self._errors.append(error)
            if len(self._errors) > self._max_size:
                self._errors.pop(0)
    
    @property
    def sessions(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return self._sessions
    
    def add_session(self, session_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._sessions[session_id] = data
    
    def remove_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._sessions.get(session_id)


# Global thread-safe store
store = ThreadSafeStore(max_size=100)


# ==================== TOP-LEVEL IMPORTS ====================

from models.config import config as app_config
from models.settings import settings

logger = logging.getLogger(__name__)


# ==================== LIFESPAN HANDLER ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle handler"""
    # Startup
    logger.info("Starting UI-Pro API...")
    
    # Pre-warm connections
    try:
        from services.streaming import get_streaming_service
        get_streaming_service()
        logger.info("Streaming service initialized")
    except Exception as e:
        logger.warning(f"Streaming service not available: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down UI-Pro API...")
    
    # Cleanup sessions
    store.sessions.clear()
    logger.info("Sessions cleared")


# ==================== FASTAPI APP ====================

app = FastAPI(lifespan=lifespan)

# API Key authentication
API_KEY_HEADER = "x-api-key"


# ==================== RESPONSE MODELS ====================

class HealthResponse(BaseModel):
    status: str
    timestamp: float
    version: str
    services: dict
    system: dict | None = None


class StatusResponse(BaseModel):
    model_fast: str
    model_reasoning: str
    ollama_url: str


class ChatRequest(BaseModel):
    message: str
    model: str | None = None  # Optional model selection


class ChatResponse(BaseModel):
    result: str
    status: str = "success"
    error: str | None = None


# ==================== EXCEPTION HANDLER ====================

async def custom_exceptions(request: Request, exc: Exception):
    """Custom exception handler for detailed errors"""
    error_info = {
        "timestamp": time.time(),
        "path": str(request.url),
        "method": request.method,
        "status_code": 500,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }

    # Store error in thread-safe store
    store.add_error(error_info)

    # Log to JSON file with context
    logging.error(
        f"[{error_info['error_type']}] {error_info['message']}",
        extra={
            "path": error_info['path'],
            "method": error_info['method'],
            "traceback": error_info['traceback'],
        }
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": error_info['message'],
            "error_type": error_info['error_type'],
            "request": str(error_info['path']),
            "request_id": request.headers.get("x-request-id", None),
        },
        headers={"x-stacktrace": error_info['traceback'][:500]}  # Truncated
    )


app.add_exception_handler(Exception, custom_exceptions)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== MIDDLEWARE ====================

@app.middleware("http")
async def add_observability(request: Request, call_next: Callable):
    """Request logging and tracing middleware"""
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

def verify_api_key(request: Request) -> bool:
    """Verify API key if configured"""
    api_key = getattr(app_config.api, 'api_key', "") if hasattr(app_config, 'api') else ""

    if not api_key:
        return True

    provided_key = request.headers.get(API_KEY_HEADER, "")

    if provided_key != api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return True


# ==================== HEALTH CHECK ====================

def _check_ollama() -> str:
    """Check if Ollama is reachable"""
    import requests
    try:
        resp = requests.get(
            settings.ollama_url.replace("/api/generate", "/api/tags"),
            timeout=2
        )
        return "ok" if resp.status_code == 200 else "unreachable"
    except Exception:
        return "unreachable"


# ==================== ROUTES ====================

@app.get("/")
def home(request: Request):
    return HTMLResponse(content=f"""
<!DOCTYPE html>
<html>
<head><title>UI Pro</title></head>
<body>
    <h1>UI Pro - LLM Orchestration Platform</h1>
    <p>🚀 Agent Orchestration System Ready</p>
    <p>Status: <strong>✅ Running</strong></p>
    <p>Models: <code>{settings.model_fast or 'N/A'}</code> + <code>{settings.model_reasoning or 'N/A'}</code></p>
    <p>⚡ Powered by <strong>Ollama</strong> + <strong>FastAPI</strong></p>
    
    <h2>Endpoints</h2>
    <ul>
        <li><code>GET /</code> - Dashboard</li>
        <li><code>GET /status</code> - API Info</li>
        <li><code>GET /health</code> - Health Check</li>
        <li><code>WS /ws</code> - Agent Stream</li>
    </ul>
</body>
</html>
""")


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for container orchestration"""
    system_info = _get_system_info()
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": getattr(app_config, 'version', "1.0.0"),
        "services": {
            "api": "ok",
            "llm": _check_ollama(),
        },
        "system": system_info
    }


def _get_system_info() -> dict:
    """Get system info including GPU metrics"""
    system_info: dict = {}
    
    try:
        import psutil
        system_info["cpu_percent"] = psutil.cpu_percent()
        system_info["memory_percent"] = psutil.virtual_memory().percent
    except ImportError:
        system_info["cpu_percent"] = None
        system_info["memory_percent"] = None
    
    # Try to get GPU info
    gpu_info = _get_gpu_info()
    if gpu_info:
        system_info["gpu"] = gpu_info
    
    return system_info


def _get_gpu_info() -> dict | None:
    """Get GPU utilization and memory usage"""
    # Try pynvml first (NVIDIA GPU)
    try:
        import pynvml
        pynvml.nvmlInit()
        
        # Get first GPU
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        
        # Utilization
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_util = util.gpu
        memory = util.memory
        
        # Memory info
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        mem_used_mb = mem_info.used / (1024 * 1024)
        mem_total_mb = mem_info.total / (1024 * 1024)
        mem_percent = (mem_info.used / mem_info.total) * 100
        
        # Temperature
        try:
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            temp = None
        
        pynvml.nvmlShutdown()
        
        return {
            "name": "NVIDIA GPU",
            "utilization": gpu_util,
            "memory_used_mb": round(mem_used_mb, 1),
            "memory_total_mb": round(mem_total_mb, 1),
            "memory_percent": round(mem_percent, 1),
            "temperature": temp,
        }
    except ImportError:
        pass
    except Exception:
        pass
    
    # Try nvidia-ml-py3 as fallback
    try:
        import pynvml
    except ImportError:
        pass
    
    return None


@app.get("/status", response_model=StatusResponse, dependencies=[Depends(verify_api_key)])
def status():
    return {
        "model_fast": settings.model_fast or "N/A",
        "model_reasoning": settings.model_reasoning or "N/A",
        "ollama_url": settings.ollama_url or "http://localhost:11434",
    }


@app.get("/api/settings/default-model")
def get_default_model():
    """Return the default model from settings (.env)"""
    return {
        "model_fast": settings.model_fast or "qwen3.5:0.8b",
        "model_reasoning": settings.model_reasoning or "qwen3.5:0.8b",
    }


# ==================== WEBSOCKET ====================

from controllers.websocket import get_websocket_controller


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time streaming
    
    Delegates to WebSocketController (no business logic here)
    """
    controller = get_websocket_controller()

    client_info = str(ws.client.host) if ws.client and ws.client.host else "unknown"
    try:
        await ws.accept()
        session_id = await controller.handle_connection(ws, client_info)

        try:
            while True:
                raw = await ws.receive_text()
                # Parse JSON if valid, extract model and message
                try:
                    msg_data = json.loads(raw)
                    task = msg_data.get('message', raw)
                    model = msg_data.get('model')
                    logger.info(f"[WS] Received model: {model}, task: {task[:50]}...")
                except (json.JSONDecodeError, TypeError):
                    task = raw
                    model = None
                    logger.warning(f"[WS] Non-JSON message received")
                await controller.handle_message(ws, session_id, task, model=model or None)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected normally")
        except Exception as e:
            logger.error("WebSocket error: %s", e, exc_info=True)
            try:
                await ws.send_json({
                    "type": "error",
                    "error": str(e),
                    "timestamp": time.time()
                })
            except Exception:
                pass
        finally:
            await controller.handle_disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")


# ==================== STREAMING ====================

async def sse_stream(generator):
    """Convert StreamChunk objects to SSE format"""
    async for chunk in generator:
        yield f"data: {json.dumps(chunk.to_dict())}\n\n"


from services.streaming import get_streaming_service


@app.get("/stream")
async def stream_endpoint(prompt: str):
    """SSE streaming endpoint with error handling"""
    if not prompt or len(prompt) > 10000:
        raise HTTPException(
            status_code=400,
            detail="Prompt must be non-empty and less than 10KB"
        )

    service = get_streaming_service()

    try:
        generator = service.stream_generate(prompt)
        return StreamingResponse(
            sse_stream(generator),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(
            f"Stream generation failed: {type(e).__name__}: {str(e)}",
            extra={"prompt_preview": prompt[:50]}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Stream generation failed: {str(e)}"
        )


# ==================== CHAT ENDPOINT (FALLBACK) ====================

from services.streaming import get_streaming_service


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat endpoint for REST API (fallback when WebSocket fails)"""
    try:
        stream_service = get_streaming_service()
        
        # Collect full response from streaming
        chunks = []
        async for chunk in stream_service.stream_generate(request.message, model=request.model):
            if chunk.text:
                chunks.append(chunk.text)
        
        result_text = "".join(chunks)
        return ChatResponse(result=result_text)

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return ChatResponse(result=f"Error: {str(e)}", status="error", error=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)