"""Shared mixin for OpenAI-compatible chat completions backends.

LM Studio, Lemonade, and llama.cpp all speak the same wire format
(/v1/chat/completions with SSE delta streaming). This mixin provides
the shared generate/stream/astream implementation so each backend only
needs to override health_check() and list_models().
"""

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


class OpenAICompatMixin:
    """Mixin for backends using OpenAI-compatible /v1/chat/completions.

    Must be used with a class that also inherits from LLMBackend.
    """

    backend_name: str = ""

    def _base_url(self) -> str:
        raw = self.config.url.rstrip("/")
        return raw.replace("/v1/chat/completions", "").replace("/v1/completions", "")

    def _messages(self, prompt: str, **kwargs: object) -> list[dict]:
        msgs: list[dict] = []
        system = kwargs.get("system_prompt")
        if system:
            msgs.append({"role": "system", "content": str(system)})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def generate(self, prompt: str, **kwargs: object) -> str:
        url = f"{self._base_url()}/v1/chat/completions"
        payload: dict = {
            "model": self.config.model,
            "messages": self._messages(prompt, **kwargs),
            "stream": False,
            "temperature": kwargs.get("temperature", 0.7),
        }
        # Cast self to LLMBackend for _request access
        backend: LLMBackend = self  # type: ignore[assignment]
        resp = backend._request("POST", url, json=payload).json()
        choices = resp.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        url = f"{self._base_url()}/v1/chat/completions"
        payload: dict = {
            "model": self.config.model,
            "messages": self._messages(prompt, **kwargs),
            "stream": True,
            "temperature": kwargs.get("temperature", 0.7),
        }
        backend: LLMBackend = self  # type: ignore[assignment]
        with requests.post(
            url, json=payload, stream=True, timeout=backend.config.timeout
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                text = backend._parse_sse_line(line)
                if text is None:
                    continue
                try:
                    data = json.loads(text)
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    finish_reason = choices[0].get("finish_reason")
                    if content:
                        yield content
                    if finish_reason:
                        return
                except json.JSONDecodeError:
                    logger.warning(
                        "%s parse error: %s",
                        backend.backend_name,
                        text[:60],
                    )
                    continue

    async def astream(self, prompt: str, **kwargs: object) -> AsyncGenerator[str, None]:
        loop = __import__("asyncio", fromlist=[""]).get_running_loop()
        q: Any = __import__("queue", fromlist=[""]).Queue()
        sentinel = None
        backend: LLMBackend = self  # type: ignore[assignment]

        def _produce() -> None:
            try:
                for token in self.stream(prompt, **kwargs):  # type: ignore[attr-defined]
                    q.put(("token", token))
            except Exception as e:
                logger.error("%s async stream failed: %s", backend.backend_name, e)
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
            yield str(value)


__all__ = ["OpenAICompatMixin"]
