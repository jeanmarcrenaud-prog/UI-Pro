# api/main.py - FastAPI Application Entry Point
#
# Role: FastAPI app initialization and WebSocket endpoint
# Used by: Direct uvicorn run, run.py launcher
# - /ws: WebSocket streaming with resume support
# - /api/chat: REST fallback
# - Session management
# - /logs: Log streaming

from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import json
import time
import asyncio
import uuid
import shlex
from pathlib import Path

# Suppress noise
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

# Import config
from settings import settings
from services.streaming import get_streaming_service

# === CONSTANTS ===
API_KEY_HEADER = "x-api-key"
SESSION_TTL = 3600
MAX_MESSAGES_PER_SESSION = 20
MAX_SESSIONS = 1000

# ===================== GLOBAL STORES =====================
sessions: Dict[str, Dict[str, Any]] = {}
active_requests: Dict[str, Dict[str, Any]] = {}  # message_id -> state
_log_subscriptions: set = set()  # Log streaming clients

# ===================== SESSION CLEANUP =====================


def cleanup_sessions():
    """Remove expired and excess sessions"""
    now = time.time()

    # Remove expired
    expired = [sid for sid, data in sessions.items()
             if now - data.get("last_activity", 0) > SESSION_TTL]
    for sid in expired:
        sessions.pop(sid, None)

    if expired:
        logger.info(f"Cleaned up {len(expired)} expired sessions")

    # Enforce max sessions limit
    if len(sessions) >= MAX_SESSIONS:
        oldest_sid = min(sessions.keys(), key=lambda k: sessions[k].get("last_activity", 0))
        sessions.pop(oldest_sid, None)
        logger.info("Removed oldest session due to MAX_SESSIONS limit")


# ===================== MODELS =====================
class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    provider: Optional[str] = None  # ollama, lmstudio, lemonade, llamacpp


class ChatResponse(BaseModel):
    result: str
    status: str = "success"


# ===================== DEPENDENCIES =====================
def verify_api_key(request: Request):
    api_key = getattr(settings, "api_key", None)
    if not api_key:
        return True
    if request.headers.get(API_KEY_HEADER) != api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


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


# ===================== BASIC ROUTES =====================
@app.get("/")
async def home():
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head><title>UI Pro</title></head>
    <body>
        <h1>UI Pro - LLM Orchestration Platform</h1>
        <p>Agent Orchestration System Ready</p>
        <p>Status: <strong>Running</strong></p>
        <p>Models: <code>{settings.model_fast or 'N/A'}</code> + <code>{settings.model_reasoning or 'N/A'}</code></p>
        <p>Powered by <strong>Ollama</strong> + <strong>FastAPI</strong></p>
        
        <h2>Endpoints</h2>
        <ul>
            <li><code>GET /</code> - Dashboard</li>
            <li><code>GET /status</code> - API Info</li>
            <li><code>GET /health</code> - Health Check</li>
            <li><code>WS /ws</code> - Agent Stream</li>
            <li><code>WS /logs</code> - Log Stream</li>
        </ul>
    </body>
    </html>
    """)


@app.get("/health")
async def health():
    # Get basic system info
    import psutil
    return {
        "status": "ok",
        "timestamp": time.time(),
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
        }
    }


@app.get("/status", dependencies=[Depends(verify_api_key)])
async def status():
    return {
        "model_fast": settings.model_fast,
        "model_reasoning": settings.model_reasoning,
        "ollama_url": settings.ollama_url,
    }


@app.get("/api/models", dependencies=[Depends(verify_api_key)])
async def get_models():
    """Proxy endpoint to fetch models from Ollama (avoids CORS issues)"""
    try:
        ollama_url = settings.ollama_url or "http://localhost:11434"

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")

            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                return {
                    "models": [{"id": m["name"], "name": m["name"], "provider": "ollama"} for m in models],
                    "status": "ok"
                }
            return {"models": [], "status": "error", "message": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"models": [], "status": "error", "message": str(e)}


@app.get("/api/settings/default-model")
def get_default_model():
    """Return the default model from settings"""
    return {
        "model_fast": settings.model_fast or "qwen3.5:9b",
        "model_reasoning": settings.model_reasoning or "qwen3.5:9b",
    }


# ===================== CHAT ENDPOINT (REST FALLBACK) =====================
@app.post("/api/chat", dependencies=[Depends(verify_api_key)])
async def chat(request: ChatRequest):
    """Chat endpoint (REST fallback when WebSocket fails)"""
    try:
        from services.streaming import get_streaming_service
        stream_service = get_streaming_service()

        # Collect full response from streaming (async)
        chunks = []
        async for chunk in stream_service.stream_generate(
            request.message, 
            model=request.model or settings.model_fast,
            provider=request.provider
        ):
            if chunk.text:
                chunks.append(chunk.text)

        result_text = "".join(chunks)
        return ChatResponse(result=result_text, status="success")

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return ChatResponse(result=f"Error: {str(e)}", status="error")


# ===================== EXECUTE ENDPOINT =====================
class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 30
    args: Optional[str] = None  # Command line arguments
    env: Optional[dict] = None  # Environment variables
    run_validation: bool = False  # Run validation check


class ExecuteResponse(BaseModel):
    result: str
    status: str = "ok"
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    errors: List[str] = []
    warnings: List[str] = []


@app.post("/api/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest):
    """Execute Python code in sandbox"""
    import tempfile
    start = time.time()
    logger.info(f"[EXECUTE] received code: {request.code[:50]}...")
    
    try:
        if request.language == "python":
            from core.executor import CodeExecutor
            executor = CodeExecutor(timeout=request.timeout)
            
            # Log the execution command (useful for debugging)
            main_file = Path(__file__).parent.parent.parent / "main.py"
            cmd = ["python", str(main_file)]
            if request.args:
                cmd.extend(shlex.split(request.args))
                logger.info(f"[EXECUTE] running command: {' '.join(cmd)}")
            
            result = executor.run(
                code=request.code,
                args=request.args or "",
            )
            
            logger.info(f"[EXECUTE] result keys: {result.keys()}")
            logger.info(f"[EXECUTE] stdout: {repr(result.get('stdout', ''))}")
            logger.info(f"[EXECUTE] success: {result.get('success')}")
            
            # Run validation if requested
            errors = []
            warnings = []
            if request.validate:
                import ast
                try:
                    tree = ast.parse(request.code)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ExceptHandler) and node.type is None:
                            warnings.append("Bare 'except:' clause caught. Consider specifying exception types.")
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name):
                                if node.func.id == 'print':
                                    warnings.append("print() statement detected.")
                                elif node.func.id in ('eval', 'exec'):
                                    warnings.append(f"Potential security issue: {node.func.id}()")
                except SyntaxError as e:
                    errors.append(f"Syntax error: {e.msg} at line {e.lineno}")
            
            return ExecuteResponse(
                result=result.get("stdout", ""),
                status="ok" if result.get("success", True) else "error",
                error=result.get("stderr") or result.get("error"),
                execution_time_ms=(time.time() - start) * 1000,
                errors=errors,
                warnings=warnings
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


# ===================== VALIDATE ENDPOINT =====================
class ValidateRequest(BaseModel):
    code: str
    language: str = "python"


class ValidateResponse(BaseModel):
    errors: List[str] = []
    warnings: List[str] = []
    status: str = "ok"
    error: Optional[str] = None


@app.post("/api/validate", response_model=ValidateResponse)
async def validate(request: ValidateRequest):
    """Analyze Python code for errors and warnings without execution"""
    logger.info(f"[VALIDATE] analyzing code...")
    
    try:
        if request.language == "python":
            import ast
            import warnings as py_warnings
            
            errors: List[str] = []  # type: ignore[annotation-type-check]
            warnings: List[str] = []  # type: ignore[annotation-type-check]
            
            try:
                tree = ast.parse(request.code)
                
                # Check for common issues
                for node in ast.walk(tree):
                    # Check for bare except
                    if isinstance(node, ast.ExceptHandler):
                        if node.type is None:
                            warnings.append("Bare 'except:' clause caught. Consider specifying exception types.")
                    
                    # Check for print statements (often used for debugging)
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == 'print':
                            warnings.append("print() statement detected. Consider using a logging module instead.")
                    
                    # Check for eval/use
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec'):
                            warnings.append(f"Potential security issue: {node.func.id}() can be dangerous.")
                    
                    # Check for unused imports
                    # Note: This is a simplified check - real linters do more
                
            except SyntaxError as e:
                errors.append(f"Syntax error: {e.msg} at line {e.lineno}")
            
            # Run with python -m py_compile for additional checks
            import py_compile
            try:
                py_compile.compile(request.code, '<string>', doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f"Compilation error: {str(e)}")
            
            return ValidateResponse(
                errors=errors,
                warnings=warnings,
                status="ok"
            )
        else:
            return ValidateResponse(
                status="error",
                error=f"Language not supported: {request.language}"
            )
            
    except Exception as e:
        logger.error(f"Validate error: {e}")
        return ValidateResponse(
            status="error",
            error=str(e)
        )


# ===================== INSTALL DEPENDENCIES ENDPOINT =====================
class InstallDepsRequest(BaseModel):
    code: str


class InstallDepsResponse(BaseModel):
    status: str = "ok"
    message: Optional[str] = None
    installed: Optional[List[str]] = None
    missing: Optional[List[str]] = None
    error: Optional[str] = None


@app.post("/api/install-deps", response_model=InstallDepsResponse)
async def install_deps(request: InstallDepsRequest):
    """Parse imports and auto-install missing packages"""
    logger.info(f"[INSTALL-DEPS] analyzing code...")
    
    try:
        import ast
        import subprocess
        import sys
        
        # Parse the code to extract imports
        imports = set()
        try:
            tree = ast.parse(request.code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except SyntaxError:
            return InstallDepsResponse(status="error", error="Invalid Python syntax")
        
        # Filter out standard library modules
        stdlib = {'os', 'sys', 'json', 're', 'math', 'time', 'datetime', 'random', 'collections', 
                 'itertools', 'functools', 'operator', 'string', 'io', 'logging', 'typing'}
        external = [imp for imp in imports if imp not in stdlib and not imp.startswith('_')]
        
        if not external:
            return InstallDepsResponse(
                status="ok",
                message="No external dependencies found",
                installed=[]
            )
        
        # Check which are already installed
        missing = []
        installed = []
        for pkg in external:
            try:
                __import__(pkg)
                installed.append(pkg)
            except ImportError:
                missing.append(pkg)
        
        if not missing:
            return InstallDepsResponse(
                status="ok",
                message=f"All dependencies already installed: {', '.join(installed)}",
                installed=installed
            )
        
        # Install missing packages
        logger.info(f"[INSTALL-DEPS] Installing: {missing}")
        install_results = []
        for pkg in missing:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg, "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                install_results.append(pkg)
                logger.info(f"[INSTALL-DEPS] Installed: {pkg}")
            except Exception as e:
                logger.warning(f"[INSTALL-DEPS] Failed to install {pkg}: {e}")
        
        return InstallDepsResponse(
            status="ok",
            message=f"Installed {len(install_results)} package(s)",
            installed=install_results,
            missing=[p for p in missing if p not in install_results]
        )
        
    except Exception as e:
        logger.error(f"Install deps error: {e}")
        return InstallDepsResponse(status="error", error=str(e))


# ===================== WEBSOCKET WITH RESUME SUPPORT =====================
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """WebSocket endpoint with proper resume support via active_requests"""
    await websocket.accept()

    # API Key check (after accept)
    api_key = getattr(settings, "api_key", None)
    if api_key:
        if websocket.headers.get(API_KEY_HEADER) != api_key:
            await websocket.close(code=1008, reason="Invalid API key")
            return

    client_host = websocket.client.host if websocket.client else "unknown"
    session_id = f"{client_host}-{uuid.uuid4().hex[:8]}"

    # Initialize session
    now = time.time()
    sessions[session_id] = {
        "messages": [],
        "created_at": now,
        "last_activity": now
    }

    stream_service = get_streaming_service()
    last_cleanup = time.time()
    current_message_id: Optional[str] = None

    logger.info(f"[WS] New connection: {session_id}")

    try:
        while True:
            if time.time() - last_cleanup > 60:
                cleanup_sessions()
                last_cleanup = time.time()

            data = await websocket.receive_text()
            sessions[session_id]["last_activity"] = time.time()

            # Parse incoming message
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                msg = {"message": data}

            # Handle control messages
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "message_id": current_message_id}))
                continue

            if msg.get("type") == "cancel":
                if current_message_id:
                    active_requests.pop(current_message_id, None)
                break

            # Extract request data
            task = msg.get("message") or msg.get("prompt") or ""
            model = msg.get("model")
            provider = msg.get("provider") or "lmstudio"  # Default to lmstudio
            message_id = msg.get("message_id") or str(uuid.uuid4())
            last_chunk_index: int = int(msg.get("last_chunk_index", 0) or 0)
            
            print(f"[WS-API] Received: model={model}, provider={provider}, task={task[:50]}...", flush=True)

            current_message_id = message_id

            if not model:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Model is required",
                    "message_id": message_id
                }))
                continue

            # Initialize or get request state for resume
            if message_id not in active_requests:
                active_requests[message_id] = {
                    "model": model,
                    "task": task,
                    "chunk_index": 0,
                    "is_complete": False
                }

            request_state = active_requests[message_id]
            start_chunk = max(last_chunk_index, request_state["chunk_index"])

            # Send resume acknowledgment
            if last_chunk_index > 0:
                await websocket.send_text(json.dumps({
                    "type": "resume_ack",
                    "message_id": message_id,
                    "resuming_from": last_chunk_index,
                    "current_chunk": start_chunk
                }))
                logger.info(f"[WS] Resuming {message_id} from chunk {last_chunk_index}")

            # === Step Flow ===
            await websocket.send_text(json.dumps({
                "type": "step",
                "step_id": "step-analyzing",
                "title": "Analyzing request",
                "status": "done",
                "message_id": message_id,
                "chunk_index": start_chunk
            }))

            await websocket.send_text(json.dumps({
                "type": "step",
                "step_id": "step-planning",
                "title": "Planning solution",
                "status": "active",
                "message_id": message_id,
                "chunk_index": start_chunk
            }))

            # === Token Streaming with Resume Support ===
            chunk_index = start_chunk
            print(f"[WS-API] Starting stream_generate: model={model}, provider={provider}", flush=True)

            try:
                stream_gen = stream_service.stream_generate(task, model=model, provider=provider)
                async for chunk in stream_gen:
                    chunk_text = getattr(chunk, 'text', str(chunk))

                    if chunk_index < last_chunk_index:
                        chunk_index += 1
                        continue

                    chunk_index += 1
                    request_state["chunk_index"] = chunk_index
                    
                    # Track token count (approximate by counting chunks)
                    token_count = chunk_index

                    await websocket.send_text(json.dumps({
                        "type": "token",
                        "content": chunk_text,
                        "response": chunk_text,
                        "done": False,
                        "message_id": message_id,
                        "chunk_index": chunk_index,
                        "tokens": token_count
                    }))

                    # Also emit to log subscribers
                    for log_ws in list(_log_subscriptions):
                        try:
                            await log_ws.send_text(json.dumps({
                                "type": "log",
                                "message": chunk_text[:100] if chunk_text else "",
                            }))
                        except Exception as e:
                            logger.warning(f"Log subscription error: {e}")
            except Exception as stream_err:
                print(f"[WS-API] Stream error: {stream_err}", flush=True)
                logger.error(f"Stream error: {stream_err}", exc_info=True)
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Stream error: {stream_err}",
                    "message_id": message_id
                }))
                break

            # === Complete remaining steps ===
            for step_id, title in [
                ("step-planning", "Planning solution"),
                ("step-executing", "Executing"),
                ("step-reviewing", "Reviewing")
            ]:
                await websocket.send_text(json.dumps({
                    "type": "step",
                    "step_id": step_id,
                    "title": title,
                    "status": "done",
                    "message_id": message_id,
                    "chunk_index": chunk_index
                }))

            # Final done
            await websocket.send_text(json.dumps({
                "type": "done",
                "message_id": message_id,
                "chunk_index": chunk_index,
                "tokens": chunk_index
            }))

            request_state["is_complete"] = True

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Internal server error",
                "message_id": current_message_id
            }))
        except:
            pass
    finally:
        sessions.pop(session_id, None)


# ===================== LOG STREAMING =====================
@app.websocket("/logs")
async def ws_logs(websocket: WebSocket):
    """WebSocket endpoint for streaming backend logs"""
    await websocket.accept()

    # Add to subscriptions
    _log_subscriptions.add(websocket)

    logger.info("[WS LOGS] Client connected")

    try:
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"[WS LOGS] Error: {e}")
    finally:
        _log_subscriptions.discard(websocket)
        logger.info("[WS LOGS] Client disconnected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)