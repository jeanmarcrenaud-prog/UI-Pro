# api/routers/health.py - Basic routes: home, health, status, models, settings
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from typing import Optional
import time

from settings import settings

router = APIRouter(prefix="", tags=["health"])

API_KEY_HEADER = "x-api-key"


def verify_api_key(request: Request):
    api_key = getattr(settings, "api_key", None)
    if not api_key:
        return True
    if request.headers.get(API_KEY_HEADER) != api_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


@router.get("/")
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


@router.get("/health")
async def health():
    import psutil
    return {
        "status": "ok",
        "timestamp": time.time(),
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
        }
    }


@router.get("/status", dependencies=[Depends(verify_api_key)])
async def status():
    return {
        "model_fast": settings.model_fast,
        "model_reasoning": settings.model_reasoning,
        "ollama_url": settings.ollama_url,
    }


@router.get("/api/models", dependencies=[Depends(verify_api_key)])
async def get_models():
    """Proxy endpoint to fetch models from Ollama (avoids CORS issues)"""
    import httpx
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


@router.get("/api/settings/default-model")
def get_default_model():
    """Return the default model from settings"""
    return {
        "model_fast": settings.model_fast or "qwen3.6:latest",
        "model_reasoning": settings.model_reasoning or "qwen3.6:latest",
    }