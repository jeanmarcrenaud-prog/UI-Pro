"""LM Studio-specific backend client.

LM Studio exposes an OpenAI-compatible /v1/chat/completions endpoint.
"""

from __future__ import annotations

import logging

from backend.infrastructure.llm._openai_mixin import OpenAICompatMixin
from backend.infrastructure.llm.base import LLMBackend

logger = logging.getLogger(__name__)


class LMStudioBackend(OpenAICompatMixin, LLMBackend):
    """Client for LM Studio's OpenAI-compatible API."""

    backend_name = "lmstudio"

    def list_models(self) -> list[dict]:
        """Get available models from LM Studio."""
        try:
            resp = self._request("GET", f"{self._base_url()}/api/v1/models")
            data = resp.json()
            items = data.get("data", [])
            return [{"name": m.get("id", "")} for m in items if m.get("id")]
        except Exception as e:
            logger.debug("LM Studio model listing failed: %s", e)
            return []

    def health_check(self) -> dict:
        url = f"{self._base_url()}/api/v1/models"
        result = self._measure("GET", url, timeout=min(self.config.timeout, 5))
        result["model"] = self.config.model
        if result["status"] == "ok":
            models = self.list_models()
            result["available_models"] = [m["name"] for m in models[:5]]
        return result


__all__ = ["LMStudioBackend"]
