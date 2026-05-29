"""Automatic fallback between LLM backends.

If the primary backend fails (connection error, timeout),
subsequent enabled backends are tried in priority order.

Priority (from settings.backends):
  1. The configured backend (from provider/ModelConfig)
  2. Other enabled backends, ordered: ollama > lmstudio > lemonade > llamacpp
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Iterator

from backend.infrastructure.llm.models import ModelConfig
from backend.infrastructure.llm.base import LLMBackend
from backend.infrastructure.llm.errors import LLMConnectionError, LLMTimeoutError
from backend.infrastructure.llm.factory import get_backend, list_available_backends
from backend.infrastructure.llm.health import check_backend_health

logger = logging.getLogger(__name__)

_FALLBACK_PRIORITY = ["ollama", "lmstudio", "lemonade", "llamacpp"]


def _healthy_backends() -> list[str]:
    """Return list of backends that respond to health check, in priority order."""
    from models.settings import settings

    healthy: list[str] = []
    for name in _FALLBACK_PRIORITY:
        cfg = settings.backends.get(name)
        if cfg and cfg.get("enabled", False):
            url = cfg.get("url", "")
            endpoint = cfg.get("models_endpoint", "")
            if url:
                health_url = f"{url.rstrip('/')}{endpoint}"
                result = check_backend_health(health_url, timeout=1.5)
                if result.get("status") == "ok":
                    healthy.append(name)
    return healthy


def _fallback_order(primary: str) -> list[str]:
    """Return backends to try, starting with primary, then fallbacks."""
    order = [primary]
    for name in _FALLBACK_PRIORITY:
        if name != primary:
            order.append(name)
    return order


def generate_with_fallback(
    prompt: str,
    provider: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    fallback: bool = True,
) -> str:
    """Generate a response with automatic fallback between backends.

    Args:
        prompt: The user prompt.
        provider: Primary backend to try (e.g. "ollama", "lmstudio").
                  Falls back to settings.active_provider or "ollama".
        model:  Model name to use. Falls back to settings.model_fast.
        system_prompt: Optional system prompt.
        temperature: Generation temperature.
        fallback: If True, try other backends on connection error.

    Returns:
        Generated text from the first successful backend.

    Raises:
        LLMBackendError: All backends failed.
    """
    from models.settings import settings

    provider = provider or getattr(settings, "active_provider", None) or "ollama"
    model_name = model or settings.model_fast

    errors: list[str] = []
    order = _fallback_order(provider) if fallback else [provider]

    for backend_name in order:
        try:
            # Let factory build URL from settings for each backend
            backend = get_backend(backend_name)
            backend.config.model = model_name
            return backend.generate(
                prompt, system_prompt=system_prompt, temperature=temperature
            )
        except (LLMConnectionError, LLMTimeoutError) as e:
            msg = f"{backend_name}: {e}"
            logger.warning("Fallback from %s", msg)
            errors.append(msg)
            continue

    # Re-raise all collected errors
    from backend.infrastructure.llm.errors import LLMBackendError

    raise LLMBackendError(
        f"All backends failed: {'; '.join(errors)}"
    )


def stream_with_fallback(
    prompt: str,
    provider: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    fallback: bool = True,
) -> Iterator[str]:
    """Stream a response with automatic fallback between backends.

    Yields:
        Tokens from the first successful backend.

    Raises:
        LLMBackendError: All backends failed.
    """
    from models.settings import settings

    provider = provider or getattr(settings, "active_provider", None) or "ollama"
    model_name = model or settings.model_fast

    errors: list[str] = []
    order = _fallback_order(provider) if fallback else [provider]

    for backend_name in order:
        try:
            # Let factory build URL from settings for each backend
            backend = get_backend(backend_name)
            backend.config.model = model_name
            yield from backend.stream(
                prompt, system_prompt=system_prompt, temperature=temperature
            )
            return  # Stream completed successfully
        except (LLMConnectionError, LLMTimeoutError) as e:
            msg = f"{backend_name}: {e}"
            logger.warning("Fallback stream from %s", msg)
            errors.append(msg)
            continue

    from backend.infrastructure.llm.errors import LLMBackendError

    raise LLMBackendError(
        f"All backends failed for streaming: {'; '.join(errors)}"
    )


async def astream_with_fallback(
    prompt: str,
    provider: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    fallback: bool = True,
) -> AsyncGenerator[str, None]:
    """Async streaming with automatic fallback between backends.

    Yields:
        Tokens from the first successful backend.
    """
    from models.settings import settings

    provider = provider or getattr(settings, "active_provider", None) or "ollama"
    model_name = model or settings.model_fast

    errors: list[str] = []
    order = _fallback_order(provider) if fallback else [provider]

    for backend_name in order:
        try:
            # Let factory build URL from settings for each backend
            backend = get_backend(backend_name)
            backend.config.model = model_name
            async for token in backend.astream(
                prompt, system_prompt=system_prompt, temperature=temperature
            ):
                yield token
            return
        except (LLMConnectionError, LLMTimeoutError) as e:
            msg = f"{backend_name}: {e}"
            logger.warning("Fallback astream from %s", msg)
            errors.append(msg)
            continue

    from backend.infrastructure.llm.errors import LLMBackendError

    raise LLMBackendError(
        f"All backends failed for async streaming: {'; '.join(errors)}"
    )


__all__ = [
    "astream_with_fallback",
    "generate_with_fallback",
    "stream_with_fallback",
]
