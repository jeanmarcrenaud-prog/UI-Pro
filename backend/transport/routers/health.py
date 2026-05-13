# views/routers/health.py - Health and status endpoints

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict, Optional
import time

from models.settings import settings

router = APIRouter(prefix="", tags=["health"])


def _get_setting(attr: str, default: Any = None) -> Any:
    """Get setting attribute safely."""
    return getattr(settings, attr, default) or default


def _check_ollama() -> str:
    """Check if Ollama is available."""
    import requests
    try:
        resp = requests.get(f"{settings.ollama_url}/api/tags", timeout=2)
        return "ok" if resp.ok else "unavailable"
    except Exception:
        return "unavailable"


def _get_system_info() -> Dict[str, Any]:
    """Get system info including GPU metrics."""
    system_info: Dict[str, Any] = {}
    
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


def _get_gpu_info() -> Optional[Dict[str, Any]]:
    """Get GPU utilization and memory usage."""
    try:
        import pynvml
        
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        mem_used_mb = mem_info.used / (1024 * 1024)
        mem_total_mb = mem_info.total / (1024 * 1024)
        mem_percent = (mem_info.used / mem_info.total) * 100
        
        try:
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            temp = None
        
        return {
            "name": "NVIDIA GPU",
            "utilization": util.gpu,
            "memory_used_mb": round(mem_used_mb, 1),
            "memory_total_mb": round(mem_total_mb, 1),
            "memory_percent": round(mem_percent, 1),
            "temperature": temp,
        }
    except ImportError:
        pass
    except Exception:
        pass
    
    return None


# ====================== Routes ======================

@router.get("/health")
async def health_check():
    """Health check for orchestration tools (Docker, Kubernetes, etc.)"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": getattr(settings, 'version', "1.0.0"),
        "services": {
            "api": "ok",
            "llm": _check_ollama(),
        },
        "system": _get_system_info(),
    }


@router.get("/status")
async def status():
    """Current configuration status"""
    return {
        "model_fast": _get_setting('model_fast', 'N/A'),
        "model_reasoning": _get_setting('model_reasoning', 'N/A'),
        "ollama_url": _get_setting('ollama_url', 'http://localhost:11434'),
    }


@router.get("/api/settings/default-model")
async def get_default_model():
    """Default models for frontend"""
    return {
        "model_fast": _get_setting('model_fast', 'qwen3.5:0.8b'),
        "model_reasoning": _get_setting('model_reasoning', 'qwen3.5:0.8b'),
    }


class TimeoutRequest(BaseModel):
    llm_timeout: int = 300
    executor_timeout: int = 60


@router.get("/api/settings/timeouts")
async def get_timeouts():
    """Current timeout values"""
    return {
        "llm_timeout": _get_setting('llm_timeout', 300),
        "executor_timeout": _get_setting('executor_timeout', 60),
    }


@router.post("/api/settings/timeouts")
async def set_timeouts(body: TimeoutRequest):
    """Update timeout settings and persist to .env"""
    try:
        settings.set_timout(body.llm_timeout, body.executor_timeout)
        return {"status": "ok", "llm_timeout": settings.llm_timeout, "executor_timeout": settings.executor_timeout}
    except Exception as e:
        return {"status": "error", "message": str(e)}