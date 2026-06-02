"""Lemonade-specific backend client.

Lemonade exposes an OpenAI-compatible /v1/chat/completions endpoint
with a fallback to /v1/completions for some model types.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Iterator

import httpx
import requests

from backend.infrastructure.llm._openai_mixin import OpenAICompatMixin
from backend.infrastructure.llm.base import LLMBackend

logger = logging.getLogger(__name__)


class LemonadeBackend(OpenAICompatMixin, LLMBackend):
    """Client for Lemonade's OpenAI-compatible API with fallback."""

    backend_name = "lemonade"

    def generate(self, prompt: str, **kwargs: object) -> str:
        """Generate with fallback to /v1/completions if chat endpoint fails."""
        try:
            return super().generate(prompt, **kwargs)
        except Exception:
            logger.info("Lemonade chat fallback: trying /v1/completions")
            url = f"{self._base_url()}/v1/completions"
            payload: dict = {
                "model": self.config.model,
                "prompt": prompt,
                "stream": False,
                "temperature": kwargs.get("temperature", 0.7),
            }
            resp = self._request("POST", url, json=payload).json()
            return resp.get("choices", [{}])[0].get("text", resp.get("text", ""))

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Stream with fallback to /v1/completions for non-chat models."""
        try:
            yield from super().stream(prompt, **kwargs)
            return
        except Exception:
            logger.info("Lemonade chat stream fallback: trying /v1/completions")
            url = f"{self._base_url()}/v1/completions"
            payload: dict = {
                "model": self.config.model,
                "prompt": prompt,
                "stream": True,
                "temperature": kwargs.get("temperature", 0.7),
            }
            with requests.post(
                url, json=payload, stream=True, timeout=self.config.timeout
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    text = self._parse_sse_line(line)
                    if text is None:
                        continue
                    try:
                        data = json.loads(text)
                        choices = data.get("choices", [])
                        content = ""
                        if choices:
                            content = choices[0].get(
                                "text",
                                choices[0].get("delta", {}).get("content", ""),
                            )
                        else:
                            content = data.get("text", "")
                        if content:
                            yield content
                        finish = (
                            choices[0].get("finish_reason")
                            if choices
                            else data.get("finish_reason")
                        )
                        if finish:
                            return
                    except json.JSONDecodeError:
                        logger.warning("Lemonade fallback parse error: %s", text[:60])
                        continue

    async def astream(
        self, prompt: str, **kwargs: object
    ) -> AsyncGenerator[str, None]:
        """Async stream with fallback to /v1/completions on chat stream failure.

        Lemonade sometimes closes the chat-completions SSE stream mid-response
        (e.g. for non-chat models, or when VRAM is insufficient and the
        model crashes). Mirror the sync stream() behavior with an async
        fallback to /v1/completions when the chat path raises.
        """
        try:
            async for token in super().astream(prompt, **kwargs):
                yield token
            return
        except (httpx.RemoteProtocolError, httpx.RequestError) as e:
            logger.info(
                "Lemonade chat astream failed (%s) — falling back to /v1/completions",
                e.__class__.__name__,
            )
        except Exception as e:
            logger.warning(
                "Lemonade chat astream unexpected error (%s) — falling back to /v1/completions",
                e,
            )

        url = f"{self._base_url()}/v1/completions"
        payload: dict = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": True,
            "temperature": kwargs.get("temperature", 0.7),
        }

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    text = self._parse_sse_line(line.encode())
                    if text is None:
                        continue
                    try:
                        data = json.loads(text)
                        choices = data.get("choices", [])
                        content = ""
                        if choices:
                            content = choices[0].get(
                                "text",
                                choices[0].get("delta", {}).get("content", ""),
                            )
                        else:
                            content = data.get("text", "")
                        if content:
                            yield content
                        finish = (
                            choices[0].get("finish_reason")
                            if choices
                            else data.get("finish_reason")
                        )
                        if finish:
                            return
                    except json.JSONDecodeError:
                        logger.warning(
                            "Lemonade async fallback parse error: %s", text[:60]
                        )
                        continue

    def list_models(self) -> list[dict]:
        """List models via /v1/models, returns all available fields."""
        try:
            url = f"{self._base_url()}/v1/models"
            resp = self._request("GET", url).json()
            return [
                {
                    "name": m.get("id", ""),
                    "size": m.get("size"),
                    "parameter_size": m.get("parameter_size") or m.get("details", {}).get("parameter_size"),
                    "quantization_level": m.get("quantization_level") or m.get("details", {}).get("quantization_level"),
                    "family": m.get("family") or m.get("details", {}).get("family"),
                }
                for m in resp.get("data", [])
                if m.get("id")
            ]
        except Exception as e:
            logger.debug("Lemonade model listing failed: %s", e)
            return []

    def health_check(self) -> dict:
        url = f"{self._base_url()}/api/v1/models"
        result = self._measure("GET", url, timeout=min(self.config.timeout, 5))
        result["model"] = self.config.model
        return result


__all__ = ["LemonadeBackend"]
