# views/api.py - FastAPI Routes + WebSocket Endpoint
#
# Role: HTTP/HTTPS endpoints + WebSocket streaming
# Used by: Frontend (Next.js), external clients
# - /ws: Real-time streaming with resume support
# - /api/chat: REST fallback
# - /health, /status: Health checks

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
import uuid
import os
import asyncio
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


# ==================== INTERNAL IMPORTS ====================
# Note: These are imported here to avoid circular imports
# but could be moved to top if needed
from models.settings import settings
from services.streaming import get_streaming_service, StreamStatus
from controllers.websocket import get_websocket_controller


# ==================== THREAD-SAFE STATE MANAGEMENT ====================

# Session cleanup function for WebSocket
def _cleanup_sessions():
    """Remove expired sessions to prevent memory leaks"""
    now = time.time()
    # Use public sessions property
    sessions = store.sessions
    expired = [k for k, v in sessions.items() if now - v.get("last_activity", 0) > 3600]
    for k in expired:
        store.remove_session(k)
    if expired:
        logger.info(f"[CLEANUP] Removed {len(expired)} expired sessions")


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
                self._errors = self._errors[-50:]  # Keep last 50 errors only
    
    def add_session(self, session_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            # Limit total sessions to prevent memory bloat
            if len(self._sessions) >= 50:
                # Remove oldest sessions
                oldest_keys = sorted(self._sessions.keys(), key=lambda k: self._sessions[k].get("last_activity", 0))[:10]
                for k in oldest_keys:
                    self._sessions.pop(k, None)
            self._sessions[session_id] = data
    
    def remove_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._sessions.get(session_id)
    
    def clear_sessions(self) -> None:
        """Clear all sessions - called on shutdown"""
        with self._lock:
            self._sessions.clear()
    
    @property
    def sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get a copy of sessions for inspection"""
        with self._lock:
            return dict(self._sessions)


# Global thread-safe store
store = ThreadSafeStore(max_size=100)


logger = logging.getLogger(__name__)


# ==================== LIFESPAN HANDLER ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle handler"""
# Startup
    logger.info("Starting UI-Pro API...")
    
    # Pre-warm connections
    try:
        get_streaming_service()
        logger.info("Streaming service initialized")
    except Exception as e:
        logger.warning(f"Streaming service not available: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down UI-Pro API...")
    
    # Cleanup sessions
    store.clear_sessions()
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
    provider: str | None = None  # Provider: ollama, lmstudio, lemonade, llamacpp


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
        "version": getattr(settings, 'version', "1.0.0"),
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

# =====================
# WEBSOCKET RESUME STATE
# =====================
# Note: Request state is now managed by WebSocketController


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time streaming with resume support
    
    Features:
    - Proper resume via message_id + last_chunk_index
    - Request state tracking via WebSocketController
    - resume_ack confirmation
    """
    logger.info("[WS-VIEWS] WebSocket endpoint CALLED!")
    logger.info(f"[WS-VIEWS] Headers: {dict(ws.headers)}")
    client_info = str(ws.client.host) if ws.client and ws.client.host else "unknown"
    logger.info(f"[WS-VIEWS] Client: {client_info}")

    # Optional API key check
    api_key = getattr(settings, 'api_key', None)
    if api_key:
        if ws.headers.get("x-api-key") != api_key:
            await ws.close(code=1008, reason="Invalid API key")
            return

    # Use WebSocketController for state management
    ws_controller = get_websocket_controller()
    stream_service = get_streaming_service()
    current_message_id: str | None = None
    session_id: str = "unknown"

    try:
        await ws.accept()
        session_id = await ws_controller.handle_connection(ws, client_info)
        logger.info(f"[WS-VIEWS] Connection accepted from {client_info}, session_id={session_id}")

        # Track cleanup timing
        last_cleanup = time.time()

        while True:
            # Periodic cleanup every 60s
            if time.time() - last_cleanup > 60:
                _cleanup_sessions()
                await ws_controller.cleanup_completed()
                last_cleanup = time.time()

            data = await ws.receive_text()
            logger.info(f"[WS] Received: {data[:100]}...")

            # Parse message using controller
            msg = await ws_controller.parse_message(data)

            # Handle control messages
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong", "message_id": current_message_id}))
                continue

            if msg.get("type") == "cancel":
                if current_message_id:
                    await ws_controller.cancel_request(current_message_id)
                break

            # Validate request using controller
            is_valid, error_msg, request = await ws_controller.validate_request(msg)
            if not is_valid:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "message": error_msg,
                    "message_id": request.get("message_id") if request else "unknown"
                }))
                continue

            task = request["task"]
            model = request["model"]
            provider = request["provider"]
            message_id = request["message_id"]
            last_chunk_index = request["last_chunk_index"]

            current_message_id = message_id

            # Register/resume request via controller
            request_state = await ws_controller.register_request(message_id, model, task)
            start_chunk = max(last_chunk_index, request_state["chunk_index"])

            # Send resume acknowledgment
            if last_chunk_index > 0:
                await ws.send_text(json.dumps({
                    "type": "resume_ack",
                    "message_id": message_id,
                    "resuming_from": last_chunk_index,
                    "current_chunk": start_chunk
                }))
                logger.info(f"Resuming message {message_id} from chunk {last_chunk_index}")

            # === Streaming Phase (streaming service handles step events) ===
            async for chunk in stream_service.stream_generate(
                task, 
                model=model, 
                provider=provider,
                start_chunk=start_chunk
            ):
                # Handle final events from streaming service
                if chunk.status == StreamStatus.COMPLETED:
                    # Send final done signal
                    await ws.send_text(json.dumps({
                        "type": "done",
                        "message_id": message_id,
                        "chunk_index": chunk.chunk_index
                    }))
                    # Mark remaining steps as done
                    for step_id, title in [
                        ("step-planning", "Planning solution"),
                        ("step-executing", "Executing"),
                        ("step-reviewing", "Reviewing")
                    ]:
                        await ws.send_text(json.dumps({
                            "type": "step",
                            "step_id": step_id,
                            "title": title,
                            "status": "done",
                            "message_id": message_id,
                            "chunk_index": chunk.chunk_index
                        }))
                    await ws_controller.update_request_state(message_id, chunk.chunk_index, is_complete=True)
                    continue

                if chunk.status == StreamStatus.ERROR:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": chunk.error or "Generation error",
                        "message_id": message_id,
                        "chunk_index": chunk.chunk_index
                    }))
                    await ws_controller.update_request_state(message_id, chunk.chunk_index, is_complete=True)
                    continue

                if chunk.status == StreamStatus.CANCELLED:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Request cancelled by user",
                        "message_id": message_id,
                        "chunk_index": chunk.chunk_index
                    }))
                    await ws_controller.update_request_state(message_id, chunk.chunk_index, is_complete=True)
                    continue

                # Handle step events from streaming service
                if chunk.step_id:
                    await ws.send_text(json.dumps({
                        "type": "step",
                        "step_id": chunk.step_id,
                        "title": chunk.step_id.replace("step-", "").replace("-", " ").title(),
                        "status": chunk.step_status,
                        "message_id": message_id,
                        "chunk_index": chunk.chunk_index
                    }))
                    await ws_controller.update_request_state(message_id, chunk.chunk_index)
                    continue

                # Handle token chunks
                if chunk.text:
                    await ws_controller.update_request_state(message_id, chunk.chunk_index)
                    await ws.send_text(json.dumps({
                        "type": "token",
                        "content": chunk.text,
                        "response": chunk.text,
                        "done": False,
                        "message_id": message_id,
                        "chunk_index": chunk.chunk_index
                    }))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        await ws_controller.handle_disconnect(session_id)
        try:
            await ws.send_text(json.dumps({
                "type": "error",
                "message": "An internal error occurred",
                "message_id": current_message_id
            }))
        except Exception:
            pass


# ==================== STREAMING ====================

async def sse_stream(generator):
    """Convert StreamChunk objects to SSE format"""
    async for chunk in generator:
        yield f"data: {json.dumps(chunk.to_dict())}\n\n"


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
        # Default model for SSE endpoint
        generator = service.stream_generate(prompt, model="qwen3.5:9b")
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


class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 30


class ExecuteResponse(BaseModel):
    result: str
    status: str = "ok"
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@app.post("/api/execute", response_model=ExecuteResponse)
async def execute_endpoint(request: ExecuteRequest):
    """Execute code in sandbox and return output"""
    import tempfile
    import asyncio
    start = time.time()
    
    try:
        if request.language == "python":
            from core.executor import CodeExecutor
            executor = CodeExecutor(timeout=request.timeout)
            
            # Execute in temp file
            result = executor.run(request.code)
            
            return ExecuteResponse(
                result=result.get("stdout", result.get("output", "")),
                status="ok" if result.get("success", True) else "error",
                error=result.get("stderr", result.get("error")),
                execution_time_ms=(time.time() - start) * 1000
            )
        else:
            return ExecuteResponse(
                result="",
                status="error",
                error=f"Language not supported: {request.language}",
                execution_time_ms=(time.time() - start) * 1000
            )
    except Exception as e:
        logger.error(f"Execute error: {e}")
        return ExecuteResponse(
            result="",
            status="error",
            error=str(e),
            execution_time_ms=(time.time() - start) * 1000
        )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat endpoint for REST API (fallback when WebSocket fails)"""
    try:
        stream_service = get_streaming_service()
        
        # Collect full response from streaming
        chunks = []
        async for chunk in stream_service.stream_generate(request.message, model=request.model or "qwen3.5:9b", provider=request.provider):
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