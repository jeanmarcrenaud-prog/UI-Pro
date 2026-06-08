"""Factory: create the right LLMBackend for a given provider name.

Mapping:
  "ollama"   -> OllamaBackend      (/api/generate)
  "lmstudio" -> LMStudioBackend    (/v1/chat/completions)
  "lemonade" -> LemonadeBackend    (/v1/chat/completions + /v1/completions)
  "llamacpp" -> LlamaCppBackend    (/v1/chat/completions)
"""

from __future__ import annotations

import logging

from backend.infrastructure.llm.models import ModelConfig
from backend.infrastructure.llm.base import LLMBackend
from backend.infrastructure.llm.errors import LLMBackendError

logger = logging.getLogger(__name__)

_BACKEND_REGISTRY: dict[str, type[LLMBackend]] = {}


def register_backend(name: str, cls: type[LLMBackend]) -> None:
    """Register a backend class for a given provider name."""
    _BACKEND_REGISTRY[name.lower()] = cls


def get_backend(provider: str, config: ModelConfig | None = None) -> LLMBackend:
    """Get the correct LLMBackend instance for the given provider.

    Raises LLMBackendError if provider is unknown.
    """
    provider = provider.lower()

    if provider not in _BACKEND_REGISTRY:
        available = ", ".join(sorted(_BACKEND_REGISTRY))
        raise LLMBackendError(
            f"Unknown provider '{provider}'. Available: {available}"
        )

    if config is None:
        from backend.domain.settings import settings

        # Build URL for this provider
        url_map = {
            "ollama": settings.ollama_url,
            "lmstudio": settings.lmstudio_url,
            "lemonade": settings.lemonade_url,
            "llamacpp": settings.llamacpp_url,
        }
        base_url = url_map.get(provider, settings.ollama_url)
        endpoint = "/api/generate" if provider == "ollama" else "/v1/chat/completions"

        # Per-provider timeout (fallback to global llm_timeout)
        backend_cfg = settings.backends.get(provider, {})
        timeout = backend_cfg.get("timeout", settings.llm_timeout)

        config = ModelConfig(
            url=f"{base_url.rstrip('/')}{endpoint}",
            model=settings.model_fast,
            timeout=timeout,
            backend=provider,
        )

    cls = _BACKEND_REGISTRY[provider]
    return cls(config)


def list_available_backends() -> list[str]:
    """Return sorted list of registered backend names."""
    return sorted(_BACKEND_REGISTRY)


# ── Auto-register available backends ───────────────────────────

def _auto_register() -> None:
    try:
        from backend.infrastructure.llm.ollama import OllamaBackend
        register_backend("ollama", OllamaBackend)
    except ImportError as e:
        logger.debug("Ollama backend not available: %s", e)

    try:
        from backend.infrastructure.llm.lmstudio import LMStudioBackend
        register_backend("lmstudio", LMStudioBackend)
    except ImportError as e:
        logger.debug("LM Studio backend not available: %s", e)

    try:
        from backend.infrastructure.llm.lemonade import LemonadeBackend
        register_backend("lemonade", LemonadeBackend)
    except ImportError as e:
        logger.debug("Lemonade backend not available: %s", e)

    try:
        from backend.infrastructure.llm.llamacpp import LlamaCppBackend
        register_backend("llamacpp", LlamaCppBackend)
    except ImportError as e:
        logger.debug("llama.cpp backend not available: %s", e)


_auto_register()

__all__ = [
    "get_backend",
    "list_available_backends",
    "register_backend",
]
