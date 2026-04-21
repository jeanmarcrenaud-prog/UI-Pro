from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import logging
import json
import time
import asyncio
import httpx
import uuid

logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

# Import config
from core.config import config as app_config

# Import settings
from settings import settings

# Get LLM router
try:
    from llm.router import LLMRouter
    llm_router = LLMRouter()
except Exception:
    llm_router = None

# API Key authentication
API_KEY_HEADER = "x-api-key"
SESSION_TTL = 3600  # 1 hour TTL for sessions (in seconds)
MAX_MESSAGES = 20  # Max messages per session to prevent memory bloat
MAX_SESSIONS = 1000  # Max total sessions

# Session storage with proper structure
sessions: dict[str, dict] = {}  # session_id -> {"messages": [], "created_at": float, "last_activity": float}

def _cleanup_sessions():
    """Remove expired sessions to prevent memory leaks"""
    import time
    now = time.time()
    
    # Remove expired sessions
    expired = [k for k, v in sessions.items() if now - v.get("last_activity", 0) > SESSION_TTL]
    for k in expired:
        del sessions[k]
    if expired:
        print(f"[SESSIONS] Cleaned up {len(expired)} expired sessions")
    
    # Enforce MAX_SESSIONS limit
    if len(sessions) >= MAX_SESSIONS:
        # Remove oldest session
        oldest = min(sessions.items(), key=lambda x: x[1].get("last_activity", 0))
        del sessions[oldest[0]]
        print(f"[SESSIONS] Removed oldest session (limit reached)")

# Chat request model
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    result: str
    status: str = "success"

# SSE Event model
class StreamEvent(BaseModel):
    """Standardized SSE event format"""
    type: str
    step_id: Optional[str] = None
    data: str
    event_id: Optional[str] = None
    stream_id: Optional[str] = None


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


# 🚀 Charger tout depuis .env via settings
app = FastAPI()
# Note: sessions already defined above with proper typing


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
def health():
    """Health check - simple and fast for container orchestration"""
    return {
        "status": "ok",
        "timestamp": time.time(),
    }


@app.get("/status", dependencies=[Depends(verify_api_key)])
def status():
    return {
        "model_fast": settings.model_fast or "N/A",
        "model_reasoning": settings.model_reasoning or "N/A",  
        "ollama_url": settings.ollama_url or "http://localhost:11434",
    }


@app.get("/api/models", dependencies=[Depends(verify_api_key)])
async def get_models():
    """Proxy endpoint to fetch models from Ollama (avoids CORS issues)
    
    Uses async httpx client to avoid blocking threads.
    Requires API key auth.
    """
    try:
        ollama_url = settings.ollama_url or "http://localhost:11434"
        
        # Use async httpx client instead of blocking requests
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
    """Return the default model from settings (.env)"""
    return {
        "model_fast": settings.model_fast or "qwen3.5:9b",
        "model_reasoning": settings.model_reasoning or "qwen3.5:9b",
    }


# Chat endpoint
@app.post("/api/chat", dependencies=[Depends(verify_api_key)])
def chat(request: ChatRequest):
    """Chat with the agent"""
    try:
        # Simple response for now - can be connected to real orchestrator
        result = f"Processing: {request.message[:100]}..."
        return {"result": result, "status": "success"}
    except Exception as e:
        return {"result": str(e), "status": "error"}


@app.get("/stream/{prompt}")
async def stream(prompt: str):
    """SSE endpoint for streaming events"""
    
    async def event_generator():
        # Send step start
        yield f"data: {json.dumps({'type': 'step', 'stepId': '1', 'data': 'Analyzing'})}\n\n"
        await asyncio.sleep(0.5)
        
        yield f"data: {json.dumps({'type': 'step', 'stepId': '1', 'data': 'done'})}\n\n"
        
        yield f"data: {json.dumps({'type': 'step', 'stepId': '2', 'data': 'active'})}\n\n"
        await asyncio.sleep(0.3)
        
        # Stream tokens (simulate response)
        response = f"Processing your request about: {prompt[:50]}... Let me analyze this and provide a helpful response. I'm currently thinking through the best approach to answer your question."
        for char in response:
            yield f"data: {json.dumps({'type': 'token', 'data': char})}\n\n"
            await asyncio.sleep(0.02)
        
        # Done
        yield f"data: {json.dumps({'type': 'step', 'stepId': '2', 'data': 'done'})}\n\n"
        yield f"data: {json.dumps({'type': 'step', 'stepId': '3', 'data': 'done'})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'data': ''})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Log subscriptions - track connected WebSocket clients for log streaming
_log_subscriptions: set = set()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """WebSocket endpoint with proper auth and session management"""
    # API key authentication
    if app_config.api.api_key:
        provided_key = ws.headers.get(API_KEY_HEADER, "")
        if provided_key != app_config.api.api_key:
            await ws.close(code=1008)
            return
    """WebSocket endpoint for real-time streaming with log events
    
    Accepts: JSON {message: "...", model?: "..."}
    Returns: Stream of JSON events with type field
      - {type: "step", ...} - Step changes
      - {type: "token", ...} - Token stream
      - {type: "tool", ...} - Tool execution
      - {type: "done", ...} - Completion
      - {type: "error", ...} - Errors
    """
    await ws.accept()
    
    # Use client info safely with UUID to avoid collisions
    client_info = str(ws.client.host) if ws.client and ws.client.host else "unknown"
    session_id = f"{client_info}-{uuid.uuid4().hex[:8]}"
    
    # Register session with proper structure
    now = time.time()
    sessions[session_id] = {"messages": [], "created_at": now, "last_activity": now}
    
    # Logger for this session
    session_logger = logging.getLogger(f"session.{session_id}")
    
    # Track cleanup timing
    last_cleanup = time.time()
    
    # Track message_id for deduplication across reconnect
    msg_id = None
    chunk_index = 0  # Track chunk order to prevent duplication
    
    try:
        while True:
            # Periodic cleanup every 60 seconds to prevent memory leaks
            if time.time() - last_cleanup > 60:
                _cleanup_sessions()
                last_cleanup = time.time()
            
            if session_id in sessions:
                # Receive message as JSON
                data = await ws.receive_text()
                sessions[session_id]["messages"].append(data)
                sessions[session_id]["last_activity"] = time.time()  # Update activity
                
                # Enforce message limit
                if len(sessions[session_id]["messages"]) > MAX_MESSAGES:
                    sessions[session_id]["messages"] = sessions[session_id]["messages"][-MAX_MESSAGES:]
                
                # Handle ping heartbeat
                try:
                    msg_data = json.loads(data)
                    # Check for ping/pong
                    if msg_data.get('type') == 'ping':
                        await ws.send_text(json.dumps({"type": "pong", "message_id": msg_id}))
                        continue
                    if msg_data.get('type') == 'cancel':
                        # Client cancelled - stop streaming
                        print(f"[WS] Client cancelled: {msg_data.get('message_id')}")
                        break
                    task = msg_data.get('message', data)
                    model = msg_data.get('model')
                    msg_id = msg_data.get('message_id')  # Track for deduplication
                    # Check for resume - client sends last_chunk_index to resume from
                    last_chunk = msg_data.get('last_chunk_index', 0)
                    # Reset chunk_index for new message OR resume from last
                    chunk_index = last_chunk
                    
                    # Send resume acknowledgment if resuming
                    if last_chunk > 0:
                        await ws.send_text(json.dumps({
                            "type": "resume",
                            "message_id": msg_id,
                            "resuming_from": last_chunk,
                            "chunk_index": chunk_index
                        }))
                        print(f"[WS] Resuming from chunk {last_chunk}")
                    
                    print(f"[WS] Received - message: {task[:30]}..., model: {model}, msg_id: {msg_id}, resume_from: {last_chunk}")
                except:
                    # Plain text fallback
                    task = data
                    model = None
                    msg_id = None
                    last_chunk = 0
                    chunk_index = 0
                    print(f"[WS] Plain text received, model: {model}")
                
                # Send step 1: Analyzing
                await ws.send_text(json.dumps({
                    "type": "step", 
                    "step_id": "step-analyzing", 
                    "title": "Analyzing request",
                    "status": "active",
                    "data": "Analyzing request...",
                    "message_id": msg_id,
                    "chunk_index": chunk_index
                }))
                
                # Use streaming service with model - no fallback!
                from services.streaming import get_streaming_service
                
                if not model:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "No model provided! Model is required.",
                        "message_id": msg_id,
                    }))
                    return
                
                print(f"[WS] Using model: {model} (user_selected)")
                
                # Stream the response
                stream_service = get_streaming_service()
                
                # Mark step 1 as done before starting stream
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-analyzing",
                    "title": "Analyzing request",
                    "status": "done",
                    "data": "Analysis complete",
                    "message_id": msg_id,
                    "chunk_index": chunk_index
                }))
                
                # Activate step 2: Planning solution
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-planning",
                    "title": "Planning solution",
                    "status": "active",
                    "data": "Planning approach...",
                    "message_id": msg_id,
                    "chunk_index": chunk_index
                }))
                
                async for chunk in stream_service.stream_generate(task, model=model):
                    # Skip chunks we've already sent (resume support)
                    if chunk_index <= last_chunk:
                        if chunk.text:
                            chunk_index += 1
                        continue
                    # Standardized format: type + content + message_id + chunk_index
                    chunk_text = chunk.text if hasattr(chunk, 'text') else ''
                    if chunk_text:
                        chunk_index += 1
                        await ws.send_text(json.dumps({
                            "type": "token",
                            "content": chunk_text,
                            "response": chunk_text,  # KEY FIX: Frontend looks for 'response' field
                            "done": False,
                            "message_id": msg_id,
                            "chunk_index": chunk_index
                        }))
                    
                    # Also emit to log subscribers (safe iteration)
                    for log_ws in list(_log_subscriptions):
                        try:
                            await log_ws.send_text(json.dumps({
                                "type": "log",
                                "message": chunk_text[:100] if chunk_text else "",
                            }))
                        except Exception:
                            pass
                
                # Mark step 2 as done
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-planning",
                    "title": "Planning solution",
                    "status": "done",
                    "data": "Plan completed",
                    "message_id": msg_id,
                    "chunk_index": chunk_index
                }))
                
                # Activate step 3: Executing
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-executing",
                    "title": "Executing",
                    "status": "active",
                    "data": "Executing code...",
                    "message_id": msg_id,
                    "chunk_index": chunk_index
                }))
                
                # Mark step 3 as done
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-executing",
                    "title": "Executing",
                    "status": "done",
                    "data": "Execution complete",
                    "message_id": msg_id,
                    "chunk_index": chunk_index
                }))
                
                # Mark step 4 (Reviewing) as done
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-reviewing",
                    "title": "Reviewing",
                    "status": "done",
                    "data": "Review complete",
                    "message_id": msg_id,
                    "chunk_index": chunk_index
                }))
                
                # Send done event with message_id for deduplication
                await ws.send_text(json.dumps({"type": "done", "data": "", "message_id": msg_id, "chunk_index": chunk_index}))
                
    except Exception as e:
        print(f"[WS] Error: {e}")
        session_logger.error(f"WebSocket error: {e}")
        # Send error to client
        try:
            await ws.send_text(json.dumps({
                "type": "error",
                "message": str(e),
                "message_id": msg_id,
                "chunk_index": chunk_index
            }))
        except:
            pass
    finally:
        # Cleanup
        if session_id in sessions:
            del sessions[session_id]


@app.websocket("/logs")
async def ws_logs(websocket: WebSocket):
    """WebSocket endpoint for streaming backend logs
    
    This endpoint streams log messages from the backend:
    - Agent step changes
    - Execution progress
    - Errors
    """
    await websocket.accept()
    
    # Add to subscriptions
    _log_subscriptions.add(websocket)
    
    print(f"[WS LOGS] Client connected")
    
    try:
        # Keep alive and forward logs
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        print(f"[WS LOGS] Error: {e}")
    finally:
        _log_subscriptions.discard(websocket)
        print(f"[WS LOGS] Client disconnected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)