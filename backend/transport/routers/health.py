# views/routers/health.py - Health and status endpoints

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

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


def _get_system_info() -> dict[str, Any]:
    """Get system info including GPU metrics."""
    system_info: dict[str, Any] = {}

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


def _get_gpu_info() -> dict[str, Any] | None:
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
    # Check dependencies
    deps = _check_dependencies()

    overall = "healthy" if all(d["ok"] for d in deps.values()) else "degraded"

    return {
        "status": overall,
        "timestamp": time.time(),
        "version": getattr(settings, "version", "1.0.0"),
        "dependencies": deps,
        "services": {
            "api": "ok",
            "llm": _check_ollama(),
        },
        "system": _get_system_info(),
    }


def _check_dependencies() -> dict[str, dict]:
    """Check all backend dependencies and return structured status."""
    deps: dict[str, dict] = {}

    # FAISS / Vector memory
    try:
        from backend.infrastructure.memory import MemoryManager

        mem = MemoryManager()
        stats = mem.get_stats() if hasattr(mem, "get_stats") else {}
        deps["memory"] = {
            "ok": True,
            "status": "available",
            "vectors": stats.get("total_vectors", stats.get("count", "unknown")),
        }
    except Exception as e:
        deps["memory"] = {"ok": False, "status": "unavailable", "error": str(e)}

    # Docker sandbox
    try:
        from backend.infrastructure.docker_sandbox import get_docker_sandbox

        sb = get_docker_sandbox()
        docker_status = sb.health_check()
        deps["docker"] = {
            "ok": docker_status.get("available", False),
            "status": "available" if docker_status.get("available") else "unavailable",
            "image": getattr(sb, "image", "ui-pro-sandbox:latest"),
        }
    except Exception as e:
        deps["docker"] = {"ok": False, "status": "unavailable", "error": str(e)}

    # Code executor
    try:
        from backend.infrastructure.code_execution import CodeExecutionService

        svc = CodeExecutionService()
        deps["executor"] = {
            "ok": True,
            "status": "available",
            "timeout": svc.TIMEOUT_SECONDS,
        }
    except Exception as e:
        deps["executor"] = {"ok": False, "status": "unavailable", "error": str(e)}

    return deps


@router.get("/status")
async def status():
    """Current configuration status"""
    return {
        "model_fast": _get_setting("model_fast", "N/A"),
        "model_reasoning": _get_setting("model_reasoning", "N/A"),
        "ollama_url": _get_setting("ollama_url", "http://localhost:11434"),
    }


@router.get("/api/models")
async def get_models():
    """Get all discovered models with loaded status"""
    from backend.infrastructure.model_discovery import get_model_discovery

    discovery = get_model_discovery()
    return {
        "models": discovery.get_models_summary(),
        "loaded_count": sum(1 for m in discovery.discover_all() if m.is_loaded),
    }


@router.get("/api/settings/default-model")
async def get_default_model():
    """Default models for frontend"""
    return {
        "model_fast": _get_setting("model_fast", "qwen3.5:0.8b"),
        "model_reasoning": _get_setting("model_reasoning", "qwen3.5:0.8b"),
    }


class TimeoutRequest(BaseModel):
    llm_timeout: int = 300
    executor_timeout: int = 60


@router.get("/api/settings/timeouts")
async def get_timeouts():
    """Current timeout values"""
    return {
        "llm_timeout": _get_setting("llm_timeout", 300),
        "executor_timeout": _get_setting("executor_timeout", 60),
    }


@router.post("/api/settings/timeouts")
async def set_timeouts(body: TimeoutRequest):
    """Update timeout settings and persist to .env"""
    try:
        settings.set_timeout(body.llm_timeout, body.executor_timeout)
        return {
            "status": "ok",
            "llm_timeout": settings.llm_timeout,
            "executor_timeout": settings.executor_timeout,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


class FullSettingsRequest(BaseModel):
    model_fast: str | None = None
    model_reasoning: str | None = None
    model_code: str | None = None
    active_preset: str | None = None
    llm_timeout: int | None = None
    executor_timeout: int | None = None
    log_level: str | None = None


@router.get("/api/settings")
async def get_all_settings():
    """Get all settings for UI sync"""
    from backend.domain.settings import DEFAULT_PRESETS

    return {
        "model_fast": _get_setting("model_fast", "qwen3.5:0.8b"),
        "model_reasoning": _get_setting("model_reasoning", "qwen3.5:0.8b"),
        "model_code": _get_setting("model_code", "qwen3.5:0.8b"),
        "active_preset": _get_setting("active_preset", "balanced"),
        "llm_timeout": _get_setting("llm_timeout", 300),
        "executor_timeout": _get_setting("executor_timeout", 60),
        "log_level": _get_setting("log_level", "INFO"),
        "ollama_url": _get_setting("ollama_url", "http://localhost:11434"),
        "presets": {
            preset_id: {
                "id": preset.id,
                "name": preset.name,
                "description": preset.description,
                "model_fast": preset.model_fast,
                "model_reasoning": preset.model_reasoning,
                "model_code": preset.model_code,
            }
            for preset_id, preset in DEFAULT_PRESETS.items()
        },
    }


@router.post("/api/settings")
async def update_settings(body: FullSettingsRequest):
    """Update multiple settings at once"""
    try:
        updates = {}

        if body.model_fast is not None:
            updates["model_fast"] = body.model_fast
        if body.model_reasoning is not None:
            updates["model_reasoning"] = body.model_reasoning
        if body.model_code is not None:
            updates["model_code"] = body.model_code
        if body.active_preset is not None:
            updates["active_preset"] = body.active_preset
        if body.llm_timeout is not None:
            updates["llm_timeout"] = body.llm_timeout
        if body.executor_timeout is not None:
            updates["executor_timeout"] = body.executor_timeout
        if body.log_level is not None:
            updates["log_level"] = body.log_level

        # Apply updates
        for key, value in updates.items():
            setattr(settings, key, value)

        return {"status": "ok", "updated": list(updates.keys())}
    except Exception as e:
        return {"status": "error", "message": str(e)}
