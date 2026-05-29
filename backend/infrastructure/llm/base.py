"""Abstract base class for all LLM backend clients."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Iterator

import requests

from backend.infrastructure.llm.models import ModelConfig
from backend.infrastructure.llm.errors import (
    LLMAuthenticationError,
    LLMBackendError,
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


class LLMBackend(ABC):
    """Abstract base for all LLM backend clients.

    Each backend (Ollama, LM Studio, Lemonade, llama.cpp) implements
    generate(), stream(), astream(), and health_check().
    """

    backend_name: str = ""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    # ── Abstract: must be overridden ──────────────────────────

    @abstractmethod
    def generate(self, prompt: str, **kwargs: object) -> str:
        """Synchronous generation — full response as string."""

    @abstractmethod
    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Synchronous streaming — yields token strings."""

    @abstractmethod
    async def astream(self, prompt: str, **kwargs: object) -> AsyncGenerator[str, None]:
        """Async streaming — yields token strings."""

    @abstractmethod
    def health_check(self) -> dict:
        """Return backend health status dict.

        Keys: status ("ok" | "error"), latency_ms (float),
              model (str), error (str | None).
        """

    # ── Shared helpers ────────────────────────────────────────

    def _request(self, method: str, endpoint: str, **kwargs: object) -> requests.Response:
        """Send HTTP request and translate errors to custom hierarchy."""
        try:
            resp = requests.request(
                method, endpoint, timeout=self.config.timeout, **kwargs  # type: ignore[arg-type]
            )
            resp.raise_for_status()
            return resp
        except requests.ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to {self.backend_name} at {endpoint}: {e}"
            ) from e
        except requests.Timeout as e:
            raise LLMTimeoutError(
                f"{self.backend_name} timed out after {self.config.timeout}s: {e}"
            ) from e
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 404:
                raise LLMModelNotFoundError(
                    f"Model '{self.config.model}' not found on {self.backend_name}"
                ) from e
            if status in (401, 403):
                raise LLMAuthenticationError(
                    f"Authentication failed for {self.backend_name}"
                ) from e
            raise LLMBackendError(f"HTTP {status} from {self.backend_name}: {e}") from e
        except requests.RequestException as e:
            raise LLMBackendError(f"{self.backend_name} request failed: {e}") from e

    @staticmethod
    def _measure(method: str, url: str, **kwargs: object) -> dict:
        """Quick health check: GET endpoint, return status + latency."""
        start = time.monotonic()
        try:
            resp = requests.request(method, url, timeout=kwargs.pop("timeout", 5.0), **kwargs)  # type: ignore[arg-type]
            resp.raise_for_status()
            ms = round((time.monotonic() - start) * 1000, 1)
            return {"status": "ok", "latency_ms": ms, "error": None}
        except requests.RequestException as e:
            ms = round((time.monotonic() - start) * 1000, 1)
            return {"status": "error", "latency_ms": ms, "error": str(e)}

    @staticmethod
    def _parse_sse_line(line: bytes) -> str | None:
        """Decode SSE line and extract content.

        Returns None for control lines (empty, [DONE], keepalive).
        """
        text = line.decode().strip()
        if not text:
            return None
        if text.startswith("data: "):
            text = text[6:]
        if not text or text == "[DONE]":
            return None
        return text


__all__ = ["LLMBackend"]
