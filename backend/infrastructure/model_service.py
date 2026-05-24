# services/model_service.py - High-level Model Management Service
#
# Role: Thin orchestration layer on top of:
# - ModelDiscovery (available models + capabilities)
# - LLMRouter (intelligent task → model routing)
# - Runtime performance tracking (latency, success rate)
#
# This service does NOT duplicate routing logic - it delegates to LLMRouter.

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Any

from models.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelPerformance:
    """Runtime performance tracking per model"""

    name: str
    total_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    latency_history: deque = field(default_factory=lambda: deque(maxlen=200))
    last_used: datetime | None = None
    last_failure: datetime | None = None

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return (self.total_calls - self.failed_calls) / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls

    @property
    def p50_latency_ms(self) -> float:
        if not self.latency_history:
            return 0.0
        return median([x for x in self.latency_history])

    @property
    def p95_latency_ms(self) -> float:
        if not self.latency_history:
            return 0.0
        sorted_lat = sorted(self.latency_history)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    def record(self, latency_ms: float, success: bool):
        self.total_calls += 1
        if latency_ms > 0:
            self.total_latency_ms += latency_ms
            self.latency_history.append(latency_ms)
        if success:
            self.last_used = datetime.now()
        else:
            self.failed_calls += 1
            self.last_failure = datetime.now()


class ModelService:
    """
    High-level service coordinating discovery, routing, and runtime metrics.

    This is a thin orchestration layer - it delegates to:
    - ModelDiscovery: for available models + capabilities
    - LLMRouter: for intelligent task → model routing
    - Performance tracking: for observability
    """

    def __init__(self):
        # Type hints for lazy-loaded dependencies
        self._discovery: Any | None = None
        self._router: Any | None = None
        self._performance: dict[str, ModelPerformance] = {}
        self._lock = threading.RLock()
        self._initialized = False

    def _ensure_init(self):
        """Lazy initialization to avoid circular imports."""
        if self._initialized:
            return

        from backend.infrastructure.llm_router import get_llm_router
        from backend.infrastructure.model_discovery import get_model_discovery

        self._discovery = get_model_discovery()
        self._router = get_llm_router()
        self._initialized = True

        logger.info("ModelService initialized")

    def discover_models(self) -> list[Any]:
        """Discover available models from all backends."""
        self._ensure_init()
        assert self._discovery is not None
        return self._discovery.discover_all()

    def route(
        self, prompt: str | None = None, mode: str | None = None
    ) -> dict[str, Any]:
        """
        Route prompt to best model using LLMRouter.

        Returns:
            Dict with 'model', 'task_type', 'confidence'
        """
        self._ensure_init()
        assert self._router is not None
        return self._router.route(prompt=prompt, mode=mode)

    def get_client(self, mode: str = "fast") -> Any:
        """
        Get properly configured LLM client for the given mode.

        Returns an OllamaClient with correct model, URL, and timeout from settings.
        """
        self._ensure_init()
        from backend.infrastructure.legacy_llm_router import LLMRouter

        router = LLMRouter()
        return router.get_for_mode(mode)

    def get_client_for_model(self, model: str, provider: str | None = None) -> Any:
        """
        Get client for specific model and provider.

        Uses explicit provider to determine backend URL.
        Strips provider prefix from model name (e.g., "lmstudio-Qwen3.5 9B" -> "Qwen3.5 9B").
        """
        self._ensure_init()
        from backend.infrastructure.legacy_llm_router import ModelConfig, OllamaClient

        # Use explicit provider - this takes priority over ModelDiscovery
        provider = (provider or "ollama").lower()
        backend_url = self._get_backend_url(provider)

        # Strip provider prefix from model name (e.g., "lmstudio-Qwen3.5 9B" -> "Qwen3.5 9B")
        clean_model = model
        for prefix in ["ollama-", "lmstudio-", "lemonade-", "llamacpp-"]:
            if model.startswith(prefix):
                clean_model = model[len(prefix) :]
                break

        # Determine endpoint based on provider
        if provider == "lmstudio" or provider == "lemonade":
            endpoint = "/v1/chat/completions"
        else:
            endpoint = "/api/generate"

        config = ModelConfig(
            url=f"{backend_url.rstrip('/')}{endpoint}",
            model=clean_model,
            timeout=settings.llm_timeout,
            backend=provider,
        )

        return OllamaClient(config)

    def _get_backend_url(self, backend: str) -> str:
        """Get URL for backend from settings."""
        mapping = {
            "ollama": settings.ollama_url,
            "lmstudio": settings.lmstudio_url,
            "lemonade": settings.lemonade_url,
            "llamacpp": settings.llamacpp_url,
        }
        return mapping.get(backend.lower(), settings.ollama_url)

    def generate(
        self,
        prompt: str,
        mode: str = "fast",
        system_prompt: str | None = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """
        Main generation entrypoint with smart routing + metrics.

        Delegates to LLMRouter for model selection, then calls LLM client.
        """
        self._ensure_init()
        assert self._router is not None
        start = time.time()
        model_name = "unknown"

        try:
            # Use router to get properly configured client
            # get_for_mode returns OllamaClient with correct config
            client = self._router.get_for_mode(mode)
            model_name = client.config.model

            response = client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                **kwargs,
            )

            latency_ms = (time.time() - start) * 1000
            self._record_performance(model_name, latency_ms, success=True)

            return response

        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            self._record_performance(model_name, latency_ms, success=False)
            logger.error(f"Generation failed: {e}")
            return f"[ModelService Error] {e!s}"

    def _record_performance(self, model_name: str, latency_ms: float, success: bool):
        with self._lock:
            if model_name not in self._performance:
                self._performance[model_name] = ModelPerformance(model_name)
            self._performance[model_name].record(latency_ms, success)

    def get_metrics(self) -> dict:
        """Get service metrics."""
        return {
            "service": "ModelService",
            "models": {
                name: {
                    "success_rate": round(perf.success_rate, 3),
                    "avg_latency_ms": round(perf.avg_latency_ms, 1),
                    "p50_latency_ms": round(perf.p50_latency_ms, 1),
                    "p95_latency_ms": round(perf.p95_latency_ms, 1),
                    "total_calls": perf.total_calls,
                    "last_used": perf.last_used.isoformat() if perf.last_used else None,
                }
                for name, perf in self._performance.items()
            },
        }

    def get_available_models(self) -> list[Any]:
        """Get list of available models."""
        return self.discover_models()


# ====================== Singleton ======================

_model_service: ModelService | None = None


def get_model_service() -> ModelService:
    global _model_service
    if _model_service is None:
        _model_service = ModelService()
    return _model_service


__all__ = ["ModelPerformance", "ModelService", "get_model_service"]
