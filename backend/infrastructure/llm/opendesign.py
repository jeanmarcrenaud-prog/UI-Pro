"""Open Design backend client.

Connects UI-Pro to the Open Design daemon's /api/chat SSE endpoint,
which in turn routes to any detected coding-agent CLI (Hermes,
Claude Code, Codex, etc.) via ACP JSON-RPC or plain stdin.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Iterator
from typing import Any

import httpx
import requests

from backend.infrastructure.llm.base import LLMBackend
from backend.infrastructure.llm.errors import LLMBackendError, LLMStreamError

logger = logging.getLogger(__name__)


class OpenDesignBackend(LLMBackend):
    """Client for Open Design daemon's /api/chat SSE endpoint.

    The daemon auto-detects available coding-agent CLIs (Hermes, Claude
    Code, Codex, …) and exposes them via a unified streaming chat API.
    This backend treats each agent as a "model" — the user picks an
    agent ID (e.g. ``"hermes"``) and the daemon spawns the right CLI.
    """

    backend_name = "opendesign"

    def _base_url(self) -> str:
        return self.config.url.rstrip("/")

    # ── Payload builders ──────────────────────────────────────────

    def _chat_payload(self, prompt: str, **kwargs: object) -> dict[str, Any]:
        return {
            "agentId": self.config.model,
            "message": prompt,
            "systemPrompt": kwargs.get("system_prompt", ""),
        }

    # ── SSE helpers ───────────────────────────────────────────────

    STOP = object()  # sentinel to stop iteration

    def _dispatch_sse(
        self, current_event: str | None, data_str: str
    ) -> str | object | Exception:
        """Route a parsed SSE data line and return a directive.

        Returns
        -------
        str
            A text token to yield to the caller.
        STOP
            The stream has finished — iteration should stop.
        Exception
            An error that should be raised.
        None
            Nothing to yield (keepalive, metadata, …).
        """
        if current_event == "agent":
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError as e:
                logger.debug("opendesign agent event parse error: %s", e)
                return None
            ev_type = data.get("type")
            if ev_type in ("text_delta", "thinking_delta"):
                delta = data.get("delta", "")
                return delta if delta else None
            if ev_type == "error":
                return LLMBackendError(data.get("message", "ACP error"))
            return None

        if current_event == "stdout":
            try:
                data = json.loads(data_str)
                chunk = data.get("chunk", "")
                return chunk if chunk else None
            except json.JSONDecodeError:
                return None

        if current_event == "error":
            try:
                data = json.loads(data_str)
                return LLMBackendError(data.get("message", str(data)))
            except json.JSONDecodeError:
                return LLMBackendError(data_str)

        if current_event == "end":
            return self.STOP

        return None

    # ── Synchronous API ───────────────────────────────────────────

    def generate(self, prompt: str, **kwargs: object) -> str:
        """Full response as a single string (sync)."""
        tokens: list[str] = []
        for chunk in self.stream(prompt, **kwargs):
            if isinstance(chunk, str):
                tokens.append(chunk)
        return "".join(tokens)

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Synchronous SSE streaming via ``requests``.

        Yields text tokens as they arrive from the daemon.
        """
        url = f"{self._base_url()}/api/chat"
        payload = self._chat_payload(prompt, **kwargs)
        current_event: str | None = None

        with requests.post(
            url, json=payload, stream=True, timeout=self.config.timeout
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                decoded = line.decode() if isinstance(line, bytes) else line
                text = decoded.strip()
                if not text:
                    current_event = None
                    continue
                if text.startswith("event: "):
                    current_event = text[7:].strip()
                    continue
                if text.startswith("data: "):
                    data_str = text[6:]
                    result = self._dispatch_sse(current_event, data_str)
                    if isinstance(result, str):
                        yield result
                    elif isinstance(result, Exception):
                        raise result
                    elif result is self.STOP:
                        return
                    # None → nothing to yield, continue
                    continue
                # id: … and :keepalive lines → ignore

    # ── Asynchronous API ──────────────────────────────────────────

    async def astream(self, prompt: str, **kwargs: object) -> AsyncGenerator[str, None]:
        """Async SSE streaming via ``httpx``.

        Yields text tokens as they arrive from the daemon.
        """
        url = f"{self._base_url()}/api/chat"
        payload = self._chat_payload(prompt, **kwargs)
        current_event: str | None = None

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout)
            ) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        text = line.strip()
                        if not text:
                            current_event = None
                            continue
                        if text.startswith("event: "):
                            current_event = text[7:].strip()
                            continue
                        if text.startswith("data: "):
                            data_str = text[6:]
                            result = self._dispatch_sse(current_event, data_str)
                            if isinstance(result, str):
                                yield result
                            elif isinstance(result, Exception):
                                raise result
                            elif result is self.STOP:
                                return
                            continue
                        # id: … and :keepalive lines → ignore
        except httpx.TimeoutException as e:
            raise LLMStreamError(
                f"opendesign stream timed out after {self.config.timeout}s: {e}"
            ) from e
        except httpx.RequestError as e:
            raise LLMBackendError(f"opendesign connection failed: {e}") from e

    # ── Discovery & health ────────────────────────────────────────

    def list_models(self) -> list[dict[str, Any]]:
        """List available agents from the daemon as model entries.

        GET /api/agents → each available agent becomes a model whose
        ``name`` is the agent ID (e.g. ``"hermes"``, ``"claude"``).
        """
        url = f"{self._base_url()}/api/agents"
        resp = self._request("GET", url)
        data = resp.json()
        agents = data.get("agents", [])
        return [
            {
                "name": agent.get("id", ""),
                "available": agent.get("available", False),
            }
            for agent in agents
            if agent.get("available")
        ]

    def health_check(self) -> dict[str, Any]:
        """Probe the daemon via GET /api/agents."""
        url = f"{self._base_url()}/api/agents"
        result = self._measure("GET", url, timeout=min(self.config.timeout, 5))
        result["model"] = self.config.model
        if result["status"] == "ok":
            try:
                agents = self.list_models()
                result["available_agents"] = [a["name"] for a in agents[:10]]
            except Exception:
                pass
        return result


__all__ = ["OpenDesignBackend"]
