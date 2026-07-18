"""Tests for the Open Design backend client.

All tests use mocked HTTP responses — no real daemon required.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from backend.infrastructure.llm.models import ModelConfig
from backend.infrastructure.llm.errors import LLMBackendError
from backend.infrastructure.llm.factory import get_backend, list_available_backends


# ── SSE mock helpers ─────────────────────────────────────────────
#
# ``requests.Response.iter_lines()`` yields one element per \n-delimited
# line of the raw byte stream.  Each element below is therefore **one
# line** of the SSE protocol (event header, data payload, or blank
# separator).


def _data_line(data: object) -> bytes:
    """SSE data line."""
    return f"data: {json.dumps(data)}".encode()


def _event_line(event: str) -> bytes:
    """SSE event header line."""
    return f"event: {event}".encode()


def _blank_line() -> bytes:
    """Blank line terminating an SSE event."""
    return b""


def _keepalive_line() -> bytes:
    """SSE keepalive comment line."""
    return b": keepalive"


def _build_agent_events(*events: dict[str, Any]) -> list[bytes]:
    """Build a mock ``iter_lines`` return value from ``agent`` events.

    Each dict becomes an ``event: agent`` + ``data: …`` pair terminated
    by a blank line.
    """
    lines: list[bytes] = []
    for ev in events:
        lines.append(_event_line("agent"))
        lines.append(_data_line(ev))
        lines.append(_blank_line())
    return lines


def _build_stdout_events(*chunks: str) -> list[bytes]:
    """Build a mock ``iter_lines`` return value from ``stdout`` events."""
    lines: list[bytes] = []
    for chunk in chunks:
        lines.append(_event_line("stdout"))
        lines.append(_data_line({"chunk": chunk}))
        lines.append(_blank_line())
    return lines


# ── Async test helpers ───────────────────────────────────────────


async def _async_iter(*lines: bytes):
    """Real async generator yielding bytes (for aiter_lines mock)."""
    for line in lines:
        yield line


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def od_config() -> ModelConfig:
    return ModelConfig(
        url="http://localhost:7456",
        model="hermes",
        timeout=10,
        backend="opendesign",
    )


# ── Factory tests ────────────────────────────────────────────────


class TestFactoryRegistration:
    def test_opendesign_listed(self):
        backends = list_available_backends()
        assert "opendesign" in backends

    def test_get_opendesign(self, od_config):
        backend = get_backend("opendesign", od_config)
        assert backend.backend_name == "opendesign"
        assert backend.config.model == "hermes"
        assert backend.config.url == "http://localhost:7456"


# ── OpenDesignBackend tests ──────────────────────────────────────


class TestOpenDesignBackend:
    """Direct unit tests for OpenDesignBackend methods."""

    # ── generate() ───────────────────────────────────────────────

    @patch("requests.post")
    def test_generate_collects_tokens(self, mock_post: MagicMock, od_config):
        """generate() should collect all SSE text_delta tokens into one str."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        lines = _build_agent_events(
            {"type": "text_delta", "delta": "Hello"},
            {"type": "text_delta", "delta": " "},
            {"type": "text_delta", "delta": "world"},
            {"type": "end", "code": 0, "status": "succeeded"},
        )
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        backend = OpenDesignBackend(od_config)
        result = backend.generate("Hello Hermes")
        assert result == "Hello world"

    @patch("requests.post")
    def test_generate_handles_empty_stream(self, mock_post: MagicMock, od_config):
        """generate() should return empty string when SSE yields no text."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        lines = _build_agent_events(
            {"type": "end", "code": 0, "status": "succeeded"},
        )
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        backend = OpenDesignBackend(od_config)
        result = backend.generate("Hi")
        assert result == ""

    # ── stream() — agent: text_delta ─────────────────────────────

    @patch("requests.post")
    def test_stream_text_delta(self, mock_post: MagicMock, od_config):
        """stream() should yield text tokens from agent:text_delta events."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        lines = _build_agent_events(
            {"type": "text_delta", "delta": "Hello"},
            {"type": "text_delta", "delta": " "},
            {"type": "text_delta", "delta": "world"},
            {"type": "end", "code": 0, "status": "succeeded"},
        )
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        backend = OpenDesignBackend(od_config)
        tokens = list(backend.stream("Hi"))
        assert tokens == ["Hello", " ", "world"]

        # Verify request payload
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["agentId"] == "hermes"
        assert call_kwargs["json"]["message"] == "Hi"

    @patch("requests.post")
    def test_stream_thinking_delta(self, mock_post: MagicMock, od_config):
        """stream() should yield tokens from agent:thinking_delta events."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        lines = _build_agent_events(
            {"type": "thinking_delta", "delta": "Let me think..."},
            {"type": "text_delta", "delta": "Answer"},
            {"type": "end", "code": 0, "status": "succeeded"},
        )
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        backend = OpenDesignBackend(od_config)
        tokens = list(backend.stream("Hi"))
        assert tokens == ["Let me think...", "Answer"]

    @patch("requests.post")
    def test_stream_stdout_fallback(self, mock_post: MagicMock, od_config):
        """stream() should yield tokens from stdout events (plain CLI fallback)."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        lines = _build_stdout_events("Hello ", "world") + [
            _event_line("end"),
            _data_line({"code": 0, "status": "succeeded"}),
            _blank_line(),
        ]
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        backend = OpenDesignBackend(od_config)
        tokens = list(backend.stream("Hi"))
        assert tokens == ["Hello ", "world"]

    # ── stream() — errors ────────────────────────────────────────

    @patch("requests.post")
    def test_stream_agent_error_raises(self, mock_post: MagicMock, od_config):
        """stream() should raise LLMBackendError on agent:error events."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        lines = _build_agent_events(
            {"type": "error", "message": "Model not found"},
        )
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        backend = OpenDesignBackend(od_config)
        with pytest.raises(LLMBackendError, match="Model not found"):
            list(backend.stream("Hi"))

    @patch("requests.post")
    def test_stream_sse_error_raises(self, mock_post: MagicMock, od_config):
        """stream() should raise LLMBackendError on top-level error events."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        lines = [
            _event_line("error"),
            _data_line({"message": "AGENT_UNAVAILABLE"}),
            _blank_line(),
        ]
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        backend = OpenDesignBackend(od_config)
        with pytest.raises(LLMBackendError, match="AGENT_UNAVAILABLE"):
            list(backend.stream("Hi"))

    @patch("requests.post")
    def test_stream_ignores_metadata(self, mock_post: MagicMock, od_config):
        """stream() should ignore metadata events (start, status, usage, keepalive)."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        lines = [
            _event_line("start"),
            _data_line({"runId": "abc", "agentId": "hermes"}),
            _blank_line(),
            _event_line("agent"),
            _data_line({"type": "status", "label": "model", "model": "gpt-4"}),
            _blank_line(),
            _event_line("agent"),
            _data_line({"type": "text_delta", "delta": "Hello"}),
            _blank_line(),
            _keepalive_line(),
            _blank_line(),
            _event_line("agent"),
            _data_line({"type": "usage", "usage": {"in": 10, "out": 5}}),
            _blank_line(),
            _event_line("agent"),
            _data_line({"type": "thinking_start"}),
            _blank_line(),
            _event_line("agent"),
            _data_line({"type": "text_delta", "delta": " world"}),
            _blank_line(),
            _event_line("end"),
            _data_line({"code": 0, "status": "succeeded"}),
            _blank_line(),
        ]
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        backend = OpenDesignBackend(od_config)
        tokens = list(backend.stream("Hi"))
        # Only text_delta tokens should pass through
        assert tokens == ["Hello", " world"]

    @patch("requests.post")
    def test_stream_skips_empty_delta(self, mock_post: MagicMock, od_config):
        """stream() should skip empty delta values."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        lines = _build_agent_events(
            {"type": "text_delta", "delta": ""},
            {"type": "text_delta", "delta": "real"},
            {"type": "end", "code": 0, "status": "succeeded"},
        )
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        backend = OpenDesignBackend(od_config)
        tokens = list(backend.stream("Hi"))
        assert tokens == ["real"]

    # ── astream() ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_astream_yields_tokens(self, od_config):
        """astream() should yield tokens like stream() but via httpx."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        sse_lines = [
            "event: agent",
            'data: {"type": "text_delta", "delta": "Hello"}',
            "",
            "event: agent",
            'data: {"type": "text_delta", "delta": " world"}',
            "",
            "event: end",
            'data: {"code": 0, "status": "succeeded"}',
            "",
        ]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines.return_value = _async_iter(*sse_lines)

        # Real classes for async context manager protocol
        # (class-level __aenter__/__aexit__ required by Python)
        class _FakeStream:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, *args):
                pass

        class _FakeClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            def stream(self, method, url, **kwargs):
                return _FakeStream(mock_resp)

        with patch(
            "backend.infrastructure.llm.opendesign.httpx.AsyncClient",
            return_value=_FakeClient(),
        ):
            backend = OpenDesignBackend(od_config)
            tokens = [t async for t in backend.astream("Hi")]
            assert tokens == ["Hello", " world"]
    @pytest.mark.asyncio
    async def test_astream_raises_on_error(self, od_config):
        """astream() should raise LLMBackendError on error events."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        sse_lines = [
            "event: error",
            'data: {"message": "Daemon error"}',
            "",
        ]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines.return_value = _async_iter(*sse_lines)

        class _FakeStream:
            def __init__(self, resp):
                self.resp = resp
            async def __aenter__(self):
                return self.resp
            async def __aexit__(self, *args):
                pass

        class _FakeClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            def stream(self, method, url, **kwargs):
                return _FakeStream(mock_resp)

        with patch(
            "backend.infrastructure.llm.opendesign.httpx.AsyncClient",
            return_value=_FakeClient(),
        ):
            backend = OpenDesignBackend(od_config)
            with pytest.raises(LLMBackendError, match="Daemon error"):
                async for _ in backend.astream("Hi"):
                    pass

    @patch("backend.infrastructure.llm.base.requests.request")
    def test_list_models(self, mock_req: MagicMock, od_config):
        """list_models() should return available agents as models."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        mock_req.return_value.json.return_value = {
            "agents": [
                {"id": "hermes", "available": True},
                {"id": "claude", "available": True},
                {"id": "codex", "available": False},
            ]
        }

        backend = OpenDesignBackend(od_config)
        models = backend.list_models()
        assert models == [
            {"name": "hermes", "available": True},
            {"name": "claude", "available": True},
        ]

    @patch("backend.infrastructure.llm.base.requests.request")
    def test_list_models_empty(self, mock_req: MagicMock, od_config):
        """list_models() should return empty list when no agents available."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        mock_req.return_value.json.return_value = {"agents": []}

        backend = OpenDesignBackend(od_config)
        assert backend.list_models() == []

    # ── health_check() ───────────────────────────────────────────

    @patch("backend.infrastructure.llm.opendesign.OpenDesignBackend.list_models")
    @patch("backend.infrastructure.llm.opendesign.OpenDesignBackend._measure")
    def test_health_check_ok(
        self, mock_measure: MagicMock, mock_list: MagicMock, od_config
    ):
        """health_check() should return ok status when daemon is reachable."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        mock_measure.return_value = {
            "status": "ok",
            "latency_ms": 2.0,
            "error": None,
        }
        mock_list.return_value = [
            {"name": "hermes", "available": True},
        ]

        backend = OpenDesignBackend(od_config)
        result = backend.health_check()
        assert result["status"] == "ok"
        assert result["model"] == "hermes"
        assert result["available_agents"] == ["hermes"]

    @patch("backend.infrastructure.llm.opendesign.OpenDesignBackend._measure")
    def test_health_check_down(
        self, mock_measure: MagicMock, od_config
    ):
        """health_check() should return error when daemon is unreachable."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        mock_measure.return_value = {
            "status": "error",
            "latency_ms": 5000.0,
            "error": "Connection refused",
        }

        backend = OpenDesignBackend(od_config)
        result = backend.health_check()
        assert result["status"] == "error"
        assert "Connection refused" in result["error"]

    # ── Request payload ──────────────────────────────────────────

    @patch("requests.post")
    def test_system_prompt_included(self, mock_post: MagicMock, od_config):
        """stream() should pass systemPrompt in the request body."""
        from backend.infrastructure.llm.opendesign import OpenDesignBackend

        lines = _build_agent_events(
            {"type": "end", "code": 0, "status": "succeeded"},
        )
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        backend = OpenDesignBackend(od_config)
        list(backend.stream("Hi", system_prompt="Be concise."))

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["systemPrompt"] == "Be concise."


# ── Integration-style: factory → backend ─────────────────────────


class TestFactoryIntegration:
    """Verify the full factory→backend wiring works."""

    def test_factory_creates_opendesign(self, od_config):
        backend = get_backend("opendesign", od_config)
        assert backend.backend_name == "opendesign"
        assert backend.config.url == "http://localhost:7456"

    @patch("requests.post")
    def test_factory_wired_stream(self, mock_post: MagicMock, od_config):
        """Full path: factory.get_backend → stream."""
        backend = get_backend("opendesign", od_config)

        lines = _build_agent_events(
            {"type": "text_delta", "delta": "factory test"},
            {"type": "end", "code": 0, "status": "succeeded"},
        )
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines

        tokens = list(backend.stream("test"))
        assert tokens == ["factory test"]
