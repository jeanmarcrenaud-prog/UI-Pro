"""Ollama-specific backend client."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import AsyncGenerator, Iterator
from typing import Any

import requests

from backend.infrastructure.llm.base import LLMBackend
from backend.infrastructure.llm.errors import LLMStreamError

logger = logging.getLogger(__name__)


_OLLAMA_STAT_FIELDS = {
    "total_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
    "done_reason",
    "load_duration",
}


class OllamaBackend(LLMBackend):
    """Client for Ollama's /api/generate endpoint."""

    backend_name = "ollama"
    last_stats: dict[str, Any] = {}

    def _base_url(self) -> str:
        return self.config.url.rstrip("/").replace("/api/generate", "")

    def _payload(self, prompt: str, stream: bool, **kwargs: object) -> dict:
        return {
            "model": self.config.model,
            "prompt": prompt,
            "system": kwargs.get("system_prompt", ""),
            "stream": stream,
            "options": {"temperature": kwargs.get("temperature", 0.7)},
        }

    def generate(self, prompt: str, **kwargs: object) -> str:
        url = f"{self._base_url()}/api/generate"
        payload = self._payload(prompt, stream=False, **kwargs)
        resp = self._request("POST", url, json=payload).json()
        self.last_stats = {k: resp.get(k) for k in _OLLAMA_STAT_FIELDS if k in resp}
        return resp.get("response", "")

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str | dict]:
        """Yield tokens, then a final stats dict."""
        url = f"{self._base_url()}/api/generate"
        payload = self._payload(prompt, stream=True, **kwargs)
        last_data: dict[str, Any] = {}
        with requests.post(url, json=payload, stream=True, timeout=self.config.timeout) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                text = self._parse_sse_line(line)
                if text is None:
                    break
                try:
                    data = json.loads(text)
                    last_data = data
                    token = data.get("response", "") or data.get("thinking", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        break
                except json.JSONDecodeError as e:
                    raise LLMStreamError(
                        f"Ollama parse error: {text[:50]}"
                    ) from e

        # Extract and yield stats from the final "done" line
        stats = {k: last_data.get(k) for k in _OLLAMA_STAT_FIELDS if k in last_data}
        if stats:
            self.last_stats = stats
            yield stats

    async def astream(self, prompt: str, **kwargs: object) -> AsyncGenerator[str | dict, None]:
        """Async wrapper via thread pool — queues sync stream."""
        loop = __import__("asyncio", fromlist=[""]).get_running_loop()
        q: Any = __import__("queue", fromlist=[""]).Queue()
        sentinel = None

        def _produce() -> None:
            try:
                for item in self.stream(prompt, **kwargs):
                    q.put(("token", item))
            except Exception as e:
                logger.error("Ollama async stream failed: %s", e)
                q.put(("error", str(e)))
            finally:
                q.put(("done", sentinel))

        thread = threading.Thread(target=_produce, daemon=True)
        thread.start()

        while True:
            kind, value = await loop.run_in_executor(None, q.get)
            if kind == "done":
                break
            if kind == "error":
                raise LLMStreamError(value)
            yield value  # str or dict

    def health_check(self) -> dict:
        url = f"{self._base_url()}/api/tags"
        result = self._measure("GET", url, timeout=min(self.config.timeout, 5))
        result["model"] = self.config.model
        return result


__all__ = ["OllamaBackend"]
