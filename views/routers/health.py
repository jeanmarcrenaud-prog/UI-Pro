# views/routers/health.py - Health and status endpoints

from fastapi import APIRouter, Depends
from typing import Any, Dict, Optional

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
def health_check() -> Dict[str, Any]:
    """Health check endpoint for container orchestration."""
    try:
        system_info = _get_system_info()
    except Exception as e:
        system_info = {"error": str(e)}
    
    return {
        "status": "healthy",
        "timestamp": __import__("time").time(),
        "version": getattr(settings, 'version', "1.0.0"),
        "services": {
            "api": "ok",
            "llm": _check_ollama(),
        },
        "system": system_info
    }


@router.get("/status")
def status() -> Dict[str, Any]:
    """Get current status of the application."""
    return {
        "model_fast": _get_setting('model_fast', 'N/A'),
        "model_reasoning": _get_setting('model_reasoning', 'N/A'),
        "ollama_url": _get_setting('ollama_url', 'http://localhost:11434'),
    }


@router.get("/api/settings/default-model")
def get_default_model() -> Dict[str, Any]:
    """Get default model configuration for frontend."""
    return {
        "model_fast": _get_setting('model_fast', 'qwen3.5:0.8b'),
        "model_reasoning": _get_setting('model_reasoning', 'qwen3.5:0.8b'),
    }