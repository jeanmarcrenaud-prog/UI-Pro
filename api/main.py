from fastapi import FastAPI, WebSocket, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import logging
import json
import time
import asyncio

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

# Chat request model
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    result: str
    status: str = "success"


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
sessions = {}


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
    import psutil
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": app_config.version if hasattr(app_config, 'version') else "1.0.0",
        "services": {
            "api": "ok",
            "llm": _check_ollama(),
        },
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
        }
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


@app.get("/api/models")
def get_models():
    """Proxy endpoint to fetch models from Ollama (avoids CORS issues)"""
    import requests
    try:
        ollama_url = settings.ollama_url or "http://localhost:11434"
        resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("models", [])
            return {
                "models": [{"id": m["name"], "name": m["name"], "provider": "ollama"} for m in models],
                "status": "ok"
            }
        return {"models": [], "status": "error", "message": "Failed to fetch models"}
    except Exception as e:
        return {"models": [], "status": "error", "message": str(e)}


@app.get("/api/settings/default-model")
def get_default_model():
    """Return the default model from settings (.env)"""
    return {
        "model_fast": settings.model_fast or "qwen3.5:0.8b",
        "model_reasoning": settings.model_reasoning or "qwen3.5:0.8b",
    }


# Chat endpoint
@app.post("/api/chat")
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
    
    # Use client info safely
    client_info = str(ws.client.host) if ws.client.host else "unknown"
    session_id = f"{client_info}-{len(sessions)}"
    sessions[session_id] = []
    
    # Logger for this session
    session_logger = logging.getLogger(f"session.{session_id}")
    
    try:
        while True:
            if session_id in sessions:
                # Receive message as JSON
                data = await ws.receive_text()
                sessions[session_id].append(data)
                
                # Parse JSON to extract message and model
                try:
                    msg_data = json.loads(data)
                    task = msg_data.get('message', data)
                    model = msg_data.get('model')
                    print(f"[WS] Received - message: {task[:30]}..., model: {model}")
                except:
                    # Plain text fallback
                    task = data
                    model = None
                    print(f"[WS] Plain text received, model: {model}")
                
                # Send step 1: Analyzing
                await ws.send_text(json.dumps({
                    "type": "step", 
                    "step_id": "step-analyzing", 
                    "title": "Analyzing request",
                    "status": "active",
                    "data": "Analyzing request..."
                }))
                
                # Use streaming service with model
                from services.streaming import get_streaming_service
                from settings import settings
                
                selected_model = model or settings.model_fast or 'qwen3.5:0.8b'
                print(f"[WS] Using model: {selected_model}")
                
                # Stream the response
                stream_service = get_streaming_service()
                
                # Mark step 1 as done before starting stream
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-analyzing",
                    "title": "Analyzing request",
                    "status": "done",
                    "data": "Analysis complete"
                }))
                
                # Activate step 2: Planning solution
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-planning",
                    "title": "Planning solution",
                    "status": "active",
                    "data": "Planning approach..."
                }))
                
                async for chunk in stream_service.stream_generate(task, model=selected_model):
                    # Send the chunk
                    await ws.send_text(json.dumps(chunk.to_dict()))
                    
                    # Also emit to log subscribers
                    for log_ws in _log_subscriptions:
                        try:
                            await log_ws.send_text(json.dumps({
                                "type": "log",
                                "message": chunk.text[:100] if chunk.text else "",
                                "status": chunk.status.value
                            }))
                        except Exception:
                            pass
                
                # Mark step 2 as done
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-planning",
                    "title": "Planning solution",
                    "status": "done",
                    "data": "Plan completed"
                }))
                
                # Activate step 3: Executing
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-executing",
                    "title": "Executing",
                    "status": "active",
                    "data": "Executing code..."
                }))
                
                # Mark step 3 as done
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-executing",
                    "title": "Executing",
                    "status": "done",
                    "data": "Execution complete"
                }))
                
                # Mark step 4 (Reviewing) as done
                await ws.send_text(json.dumps({
                    "type": "step",
                    "step_id": "step-reviewing",
                    "title": "Reviewing",
                    "status": "done",
                    "data": "Review complete"
                }))
                
                # Send done event
                await ws.send_text(json.dumps({"type": "done", "data": ""}))
                
    except Exception as e:
        print(f"[WS] Error: {e}")
        session_logger.error(f"WebSocket error: {e}")
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