"""Shared mixin for OpenAI-compatible chat completions backends.

LM Studio, Lemonade, and llama.cpp all speak the same wire format
(/v1/chat/completions with SSE delta streaming). This mixin provides
the shared generate/stream/astream implementation so each backend only
needs to override health_check() and list_models().
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Iterator

import httpx
import requests

from backend.infrastructure.llm.base import LLMBackend
from backend.infrastructure.llm.errors import LLMStreamError
from backend.infrastructure.llm.models import ModelConfig

logger = logging.getLogger(__name__)


class OpenAICompatMixin:
    """Mixin for backends using OpenAI-compatible /v1/chat/completions.

    Must be used with a class that also inherits from LLMBackend.
    """

    backend_name: str = ""

    # Provided at runtime by LLMBackend via multiple inheritance
    # (e.g. class LMStudioBackend(OpenAICompatMixin, LLMBackend))
    config: ModelConfig

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

    def _thinking_kwargs(self) -> dict:
        """Return `chat_template_kwargs` for thinking-mode control.

        Qwen3.5+, DeepSeek-R1, and OpenAI o1/o3 spend most of their
        `max_tokens` budget on internal chain-of-thought before the
        visible response. The Qwen3.5 API exposes
        `chat_template_kwargs={"enable_thinking": false}` to disable
        that, so the model jumps straight to the answer. Non-thinking
        models (lfm2.5, llama-3, mistral) ignore this parameter.

        Read at request time so runtime overrides (Settings UI) take
        effect without a restart.
        """
        try:
            from backend.domain.settings import settings
            enable = settings.get_llm_enable_thinking()
        except Exception:
            # Settings not importable in some test contexts — default
            # to OFF, which is the safer choice (visible output > thinking).
            enable = False
        return {"chat_template_kwargs": {"enable_thinking": enable}}

    def generate(self, prompt: str, **kwargs: object) -> str:
        url = f"{self._base_url()}/v1/chat/completions"
        payload: dict = {
            "model": self.config.model,
            "messages": self._messages(prompt, **kwargs),
            "stream": False,
            "temperature": kwargs.get("temperature", 0.7),
        }
        payload.update(self._thinking_kwargs())
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
        payload.update(self._thinking_kwargs())
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
        """Async streaming — native httpx, no thread pool."""
        url = f"{self._base_url()}/v1/chat/completions"
        payload: dict = {
            "model": self.config.model,
            "messages": self._messages(prompt, **kwargs),
            "stream": True,
            "temperature": kwargs.get("temperature", 0.7),
        }
        payload.update(self._thinking_kwargs())
        backend: LLMBackend = self  # type: ignore[assignment]

        # Telemetry for the "empty-response" failure mode observed in
        # production (coding_node returns a stream where every delta.content
        # is empty — role-only chunks, reasoning-only deltas, or
        # finish_reason=length cutoffs). The aggregate is logged in
        # `finally` so a single line per stream tells us exactly which of
        # these patterns triggered the empty result downstream.
        chunk_count = 0
        content_chunks = 0
        empty_content_chunks = 0
        total_content_chars = 0
        last_finish_reason: str | None = None
        last_empty_delta: dict | None = None

        try:
            async with httpx.AsyncClient(timeout=backend.config.timeout) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        chunk_count += 1
                        text = backend._parse_sse_line(line.encode())
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
                                content_chunks += 1
                                total_content_chars += len(content)
                                yield content
                            else:
                                empty_content_chunks += 1
                                last_empty_delta = delta
                            if finish_reason:
                                last_finish_reason = finish_reason
                                return
                        except json.JSONDecodeError:
                            logger.warning(
                                "%s parse error: %s",
                                backend.backend_name,
                                text[:60],
                            )
                            continue
        except httpx.TimeoutException as e:
            logger.error("%s async stream timed out: %s", backend.backend_name, e)
            raise
        except httpx.RequestError as e:
            logger.error("%s async stream failed: %s", backend.backend_name, e)
            raise
        finally:
            # One summary line per stream. WARN when no content was yielded
            # (the actual bug case the user is chasing); DEBUG otherwise so
            # normal streams stay quiet in the log.
            if chunk_count > 0:
                level = logging.WARNING if total_content_chars == 0 else logging.DEBUG
                logger.log(
                    level,
                    "%s stream summary: model=%s chunks=%d content_chunks=%d "
                    "empty_chunks=%d total_chars=%d finish_reason=%s last_empty_delta=%s",
                    backend.backend_name,
                    self.config.model,
                    chunk_count,
                    content_chunks,
                    empty_content_chunks,
                    total_content_chars,
                    last_finish_reason,
                    last_empty_delta,
                )


__all__ = ["OpenAICompatMixin"]
