from fastapi import FastAPI, WebSocket, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import logging
import time
from typing import Callable
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

# Import config
from models.config import config as app_config

# Import settings
from models.settings import settings

# Import orchestrator (old version for now)
from controllers.team import run_team

# Get LLM router
import logging
logger = logging.getLogger(__name__)
try:
    from models.llm_router import LLMRouter
    llm_router = LLMRouter()
except Exception as e:
    logger.warning("Failed to import LLMRouter: %s - running without LLM router", e)
    llm_router = None

# API Key authentication
API_KEY_HEADER = "x-api-key"

# Create FastAPI app FIRST (before middleware)
app = FastAPI()
sessions = {}


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


@app.get("/health")
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


@app.get("/status", dependencies=[Depends(verify_api_key)])
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
    await ws.accept()
    session_id = await controller.handle_connection(ws, client_info)
    
    try:
        while True:
            task = await ws.receive_text()
            await controller.handle_message(ws, session_id, task)
    except Exception:
        pass
    finally:
        await controller.handle_disconnect(session_id)


class ChatRequest(BaseModel):
    """Request schema for /api/chat"""
    message: str


class ChatResponse(BaseModel):
    """Response schema for /api/chat"""
    result: str
    status: str = "success"
    error: str | None = None


class StatusResponse(BaseModel):
    """Response schema for /status endpoint"""
    model_fast: str
    model_reasoning: str
    ollama_url: str


class HealthResponse(BaseModel):
    """Response schema for /health endpoint"""
    status: str
    timestamp: float
    version: str
    services: dict
    system: dict | None = None


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat endpoint for REST API"""
    try:
        # Import ChatService for real LLM calls
        try:
            from services.chat_service import get_chat_service
            chat_service = get_chat_service()
            result = await chat_service.execute(request.message)
            return ChatResponse(result=result.get("code", str(result)))
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