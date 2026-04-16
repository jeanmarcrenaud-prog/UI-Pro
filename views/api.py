from fastapi import FastAPI, WebSocket, Request, HTTPException, Depends
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
import logging
import time
import json
import sys
from typing import Callable, Dict, Any
import traceback
from logging.handlers import RotatingFileHandler

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


# Configure root logger with rotating file handler
log_dir = "logs"
import os
os.makedirs(log_dir, exist_ok=True)
file_handler = RotatingFileHandler(
    f"{log_dir}/app.log",
    maxBytes=10*1024*1024,  # 10MB
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

# Import config
from models.config import config as app_config

# Import settings
from models.settings import settings

# Get logger
logger = logging.getLogger(__name__)

# API Key authentication
API_KEY_HEADER = "x-api-key"

# Create FastAPI app FIRST (before middleware)
app = FastAPI()

def custom_exceptions(request, exc):
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
    
    # Store error locally (optionally to database)
    errors.append(error_info)
    if len(errors) > MAX_ERRORS_TO_STORE:
        errors.pop(0)
    
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
        headers={"x-stacktrace": error_info['traceback'][:500]}  # Truncated for debugging
    )

# API Error handling
app.add_exception_handler(Exception, custom_exceptions)
sessions = {}

# Error tracking storage
errors: list[Dict[str, Any]] = []
MAX_ERRORS_TO_STORE = 100


# Response models (must be defined before endpoints use them)
class HealthResponse(BaseModel):
    """Response schema for /health endpoint"""
    status: str
    timestamp: float
    version: str
    services: dict
    system: dict | None = None


class StatusResponse(BaseModel):
    """Response schema for /status endpoint"""
    model_fast: str
    model_reasoning: str
    ollama_url: str


class ChatRequest(BaseModel):
    """Request schema for /api/chat"""
    message: str


class ChatResponse(BaseModel):
    """Response schema for /api/chat"""
    result: str
    status: str = "success"
    error: str | None = None


# ==================== Observability Middleware ====================

@app.middleware("http")
async def add_observability(request: Request, call_next: Callable):
    """Request logging and tracing middleware"""
    start_time = time.perf_counter()
    request_id = request.headers.get("x-request-id", f"req-{int(time.time() * 1000)}")
    
    # Log request start
    logger.info(f"[{request_id}] {request.method} {request.url.path} - started")
    
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Log response
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"status={response.status_code} duration={duration_ms:.2f}ms"
        )
        
        # Add headers
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


def verify_api_key(request: Request) -> bool:
    """Verify API key if configured"""
    api_key = app_config.api.api_key if hasattr(app_config, 'api') else ""
    
    # No API key configured - allow all
    if not api_key:
        return True
    
    # Check header
    provided_key = request.headers.get(API_KEY_HEADER, "")
    
    if provided_key != api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return True


# Health check import


@app.get("/")
def home(request: Request):
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head><title>UI Pro</title></head>
<body>
    <h1>UI Pro - LLM Orchestration Platform</h1>
    <p>🚀 Agent Orchestration System Ready</p>
    <p>Status: <strong>✅ Running</strong></p>
    <p>Models: <code>{}</code> + <code>{}</code></p>
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
""".format(
        settings.model_fast or "N/A",
        settings.model_reasoning or "N/A"
    ))


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for container orchestration"""
    import time
    
    # Get system info if psutil available
    try:
        import psutil
        system_info = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
        }
    except ImportError:
        system_info = {"cpu_percent": None, "memory_percent": None}
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": app_config.version if hasattr(app_config, 'version') else "1.0.0",
        "services": {
            "api": "ok",
            "llm": _check_ollama(),
        },
        "system": system_info
    }


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


@app.get("/status", response_model=StatusResponse, dependencies=[Depends(verify_api_key)])
def status():
    return {
        "model_fast": settings.model_fast or "N/A",
        "model_reasoning": settings.model_reasoning or "N/A",  
        "ollama_url": settings.ollama_url or "http://localhost:11434",
    }

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time streaming
    
    Delegates to WebSocketController (no business logic here)
    """
    from controllers.websocket import get_websocket_controller
    
    controller = get_websocket_controller()
    
    client_info = str(ws.client.host) if ws.client.host else "unknown"
    try:
        await ws.accept()
        session_id = await controller.handle_connection(ws, client_info)
        
        try:
            while True:
                task = await ws.receive_text()
                await controller.handle_message(ws, session_id, task)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected normally")
        except Exception as e:
            logger.error("WebSocket error: %s", e, exc_info=True)
            # Send error event to client if possible
            try:
                await ws.send_json({
                    "type": "error",
                    "error": str(e),
                    "timestamp": time.time()
                })
            except:
                pass  # Connection might be closed
        finally:
            await controller.handle_disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")


# SSE Wrapper for streaming
async def sse_stream(generator):
    """Convert StreamChunk objects to SSE format"""
    import json
    async for chunk in generator:
        yield f"data: {json.dumps(chunk.to_dict())}\n\n"


# Streaming endpoint
@app.get("/stream")
async def stream_endpoint(prompt: str):
    """SSE streaming endpoint with error handling"""
    from services.streaming import get_streaming_service
    
    # Validate prompt
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
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logging.error(
            f"Stream generation failed: {type(e).__name__}: {str(e)}",
            extra={"prompt_preview": prompt[:50]}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Stream generation failed: {str(e)}"
        )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat endpoint for REST API"""
    try:
        # Import ChatService for real LLM calls
        try:
            from services.chat_service import get_chat_service
            chat_service = get_chat_service()
            result = await chat_service.execute(request.message)
            # Handle result - could be dict or string
            result_code = result.get("code") if isinstance(result, dict) else str(result)
            if isinstance(result_code, dict):
                result_code = str(result_code)
            return ChatResponse(result=result_code)
        except ImportError:
            # Fallback to run_team if ChatService not available
            logger.info(f"Chat request: {request.message[:50]}...")
            # This runs synchronously - might take a while
            import io
            import sys
            buffer = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buffer
            try:
                from controllers.team import run_team
                run_team(request.message)
            finally:
                sys.stdout = old_stdout
            output = buffer.getvalue()
            if not output:
                output = f"Executed task: {request.message[:30]}... [no output]"
            return ChatResponse(result=output)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return ChatResponse(result=f"Error: {str(e)}", status="error", error=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)