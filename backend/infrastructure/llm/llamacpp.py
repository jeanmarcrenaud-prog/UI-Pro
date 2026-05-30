"""llama.cpp-specific backend client.

llama.cpp exposes an OpenAI-compatible /v1/chat/completions endpoint
via its server binary. Default port is 8080.
"""

from __future__ import annotations

import logging

from backend.infrastructure.llm._openai_mixin import OpenAICompatMixin
from backend.infrastructure.llm.base import LLMBackend

logger = logging.getLogger(__name__)


class LlamaCppBackend(OpenAICompatMixin, LLMBackend):
    """Client for llama.cpp server's OpenAI-compatible API."""

    backend_name = "llamacpp"

    def list_models(self) -> list[dict]:
        """List models via /v1/models."""
        try:
            url = f"{self._base_url()}/v1/models"
            resp = self._request("GET", url).json()
            return [{"name": m.get("id", "")} for m in resp.get("data", [])]
        except Exception as e:
            logger.warning("llama.cpp model listing failed: %s", e)
            return []

    def health_check(self) -> dict:
        url = f"{self._base_url()}/health"
        result = self._measure("GET", url, timeout=min(self.config.timeout, 5))
        result["model"] = self.config.model
        # Fallback: try /api/tags if /health not available
        if result["status"] == "error":
            result = self._measure(
                "GET",
                f"{self._base_url()}/api/tags",
                timeout=min(self.config.timeout, 5),
            )
            result["model"] = self.config.model
        return result


__all__ = ["LlamaCppBackend"]
