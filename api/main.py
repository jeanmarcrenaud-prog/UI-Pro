from fastapi import FastAPI, WebSocket, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import logging
import json
import time
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


# Health check import

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
    import time
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
    import asyncio
    
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


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time streaming"""
    await ws.accept()
    
    # Use client info safely
    client_info = str(ws.client.host) if ws.client.host else "unknown"
    session_id = f"{client_info}-{len(sessions)}"
    sessions[session_id] = []
    
    try:
        while True:
            if session_id in sessions:
                task = await ws.receive_text()
                sessions[session_id].append(task)
                
                # Simple echo for now
                await ws.send_text(f"Echo: {task}")
                
                # Send completion marker
                await ws.send_text("[DONE]")
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)