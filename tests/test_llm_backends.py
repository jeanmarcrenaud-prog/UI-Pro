"""Tests for the new LLM backend clients (Ollama, LM Studio, Lemonade, llama.cpp).

All tests use mocked HTTP responses — no real backends required.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.infrastructure.llm.models import ModelConfig
from backend.infrastructure.llm.base import LLMBackend
from backend.infrastructure.llm.errors import (
    LLMAuthenticationError,
    LLMBackendError,
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMTimeoutError,
)
from backend.infrastructure.llm.factory import get_backend, list_available_backends


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def ollama_config() -> ModelConfig:
    return ModelConfig(
        url="http://localhost:11434/api/generate",
        model="test-model",
        timeout=10,
        backend="ollama",
    )


@pytest.fixture
def openai_config() -> ModelConfig:
    return ModelConfig(
        url="http://localhost:1234/v1/chat/completions",
        model="test-model",
        timeout=10,
        backend="lmstudio",
    )


# ── Factory tests ──────────────────────────────────────────────

class TestBackendFactory:
    def test_list_backends(self):
        backends = list_available_backends()
        assert "ollama" in backends
        assert "lmstudio" in backends
        assert "lemonade" in backends
        assert "llamacpp" in backends
        assert "hermes" in backends

    def test_get_ollama(self, ollama_config):
        backend = get_backend("ollama", ollama_config)
        assert backend.backend_name == "ollama"
        assert backend.config.model == "test-model"

    def test_get_lmstudio(self, openai_config):
        backend = get_backend("lmstudio", openai_config)
        assert backend.backend_name == "lmstudio"

    def test_get_unknown_backend(self):
        with pytest.raises(LLMBackendError, match="Unknown provider"):
            get_backend("nonexistent")

    @patch("backend.infrastructure.llm.factory.ModelConfig")
    def test_get_backend_without_config(self, mock_cfg: MagicMock):
        """Factory should build config from settings when none provided."""
        mock_cfg.return_value.timeout = 30
        mock_cfg.return_value.backend = "ollama"
        backend = get_backend("ollama")
        assert backend.backend_name == "ollama"


# ── Error translation tests ────────────────────────────────────

class TestErrorTranslation:
    """Verify _request translates HTTP errors correctly."""

    @patch("backend.infrastructure.llm.base.requests.request")
    def test_connection_error(self, mock_req: MagicMock, ollama_config):
        from backend.infrastructure.llm.ollama import OllamaBackend

        mock_req.side_effect = requests.exceptions.ConnectionError("Refused")
        backend = OllamaBackend(ollama_config)
        with pytest.raises(LLMConnectionError, match="Cannot connect"):
            backend._request("GET", "http://localhost:11434/api/tags")

    @patch("backend.infrastructure.llm.base.requests.request")
    def test_timeout_error(self, mock_req: MagicMock, ollama_config):
        from backend.infrastructure.llm.ollama import OllamaBackend

        mock_req.side_effect = requests.exceptions.Timeout("timed out")
        backend = OllamaBackend(ollama_config)
        with pytest.raises(LLMTimeoutError, match="timed out"):
            backend._request("GET", "http://localhost:11434/api/tags")

    @patch("backend.infrastructure.llm.base.requests.request")
    def test_404_error(self, mock_req: MagicMock, ollama_config):
        from backend.infrastructure.llm.ollama import OllamaBackend

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404", response=mock_resp
        )
        mock_req.return_value = mock_resp
        backend = OllamaBackend(ollama_config)
        with pytest.raises(LLMModelNotFoundError, match="not found"):
            backend._request("POST", "http://localhost:11434/api/generate")

    @patch("backend.infrastructure.llm.base.requests.request")
    def test_401_error(self, mock_req: MagicMock, ollama_config):
        from backend.infrastructure.llm.ollama import OllamaBackend

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401", response=mock_resp
        )
        mock_req.return_value = mock_resp
        backend = OllamaBackend(ollama_config)
        with pytest.raises(LLMAuthenticationError, match="Authentication"):
            backend._request("POST", "http://localhost:11434/api/generate")


# ── Ollama backend tests ───────────────────────────────────────

class TestOllamaBackend:
    @patch("backend.infrastructure.llm.base.requests.request")
    def test_generate(self, mock_req: MagicMock, ollama_config):
        from backend.infrastructure.llm.ollama import OllamaBackend

        mock_req.return_value.json.return_value = {"response": "Hello world"}
        backend = OllamaBackend(ollama_config)
        result = backend.generate("Hi")
        assert result == "Hello world"

        # Verify payload format
        call_kwargs = mock_req.call_args[1]
        assert call_kwargs["json"]["model"] == "test-model"
        assert call_kwargs["json"]["prompt"] == "Hi"
        assert call_kwargs["json"]["stream"] is False

    @patch("requests.post")
    def test_stream(self, mock_post: MagicMock, ollama_config):
        from backend.infrastructure.llm.ollama import OllamaBackend

        lines = [
            b'{"response": "Hello", "done": false}',
            b'{"response": " world", "done": false}',
            b'{"response": "", "done": true}',
        ]
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines
        backend = OllamaBackend(ollama_config)
        tokens = list(backend.stream("Hi"))
        assert tokens == ["Hello", " world"]
        assert mock_post.call_args[1]["json"]["stream"] is True


# ── LM Studio backend tests ────────────────────────────────────

class TestLMStudioBackend:
    @patch("backend.infrastructure.llm.base.requests.request")
    def test_generate(self, mock_req: MagicMock, openai_config):
        from backend.infrastructure.llm.lmstudio import LMStudioBackend

        mock_req.return_value.json.return_value = {
            "choices": [{"message": {"content": "Hello from LM Studio"}}]
        }
        backend = LMStudioBackend(openai_config)
        result = backend.generate("Hi")
        assert result == "Hello from LM Studio"

        # Verify OpenAI-compatible payload
        call_kwargs = mock_req.call_args[1]
        assert "messages" in call_kwargs["json"]
        assert call_kwargs["json"]["messages"][0]["role"] == "user"
        assert call_kwargs["json"]["stream"] is False

    @patch("backend.infrastructure.llm.base.requests.request")
    def test_generate_with_system(self, mock_req: MagicMock, openai_config):
        from backend.infrastructure.llm.lmstudio import LMStudioBackend

        mock_req.return_value.json.return_value = {
            "choices": [{"message": {"content": "OK"}}]
        }
        backend = LMStudioBackend(openai_config)
        backend.generate("Hi", system_prompt="Be helpful")
        msgs = mock_req.call_args[1]["json"]["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "Be helpful"
        assert msgs[1]["role"] == "user"

    @patch("requests.post")
    def test_stream_delta(self, mock_post: MagicMock, openai_config):
        from backend.infrastructure.llm.lmstudio import LMStudioBackend

        lines = [
            b'data: {"choices": [{"delta": {"content": "Hello"}, "finish_reason": null}]}',
            b'data: {"choices": [{"delta": {"content": " world"}, "finish_reason": null}]}',
            b'data: {"choices": [{"delta": {}}, "finish_reason": "stop"}]}',
            b'data: [DONE]',
        ]
        ctx = mock_post.return_value.__enter__.return_value
        ctx.raise_for_status.return_value = None
        ctx.iter_lines.return_value = lines
        backend = LMStudioBackend(openai_config)
        tokens = list(backend.stream("Hi"))
        assert tokens == ["Hello", " world"]

    @patch("backend.infrastructure.llm.base.requests.request")
    def test_health_check(self, mock_req: MagicMock, openai_config):
        from backend.infrastructure.llm.lmstudio import LMStudioBackend

        # First call is _measure, second is list_models via _request
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"id": "model-1"}, {"id": "model-2"}]
        }
        mock_req.return_value = mock_resp
        backend = LMStudioBackend(openai_config)
        result = backend.health_check()
        assert result["status"] == "ok"
        assert "available_models" in result
        assert result["available_models"] == ["model-1", "model-2"]


# ── Lemonade backend tests ─────────────────────────────────────

class TestLemonadeBackend:
    @patch("backend.infrastructure.llm.base.requests.request")
    def test_generate_chat(self, mock_req: MagicMock):
        from backend.infrastructure.llm.lemonade import LemonadeBackend

        mock_req.return_value.json.return_value = {
            "choices": [{"message": {"content": "Lemonade response"}}]
        }
        cfg = ModelConfig(
            url="http://localhost:13305/v1/chat/completions",
            model="test-model",
            timeout=10,
            backend="lemonade",
        )
        backend = LemonadeBackend(cfg)
        result = backend.generate("Hi")
        assert result == "Lemonade response"

    @patch("backend.infrastructure.llm.base.requests.request")
    def test_generate_fallback_to_completions(self, mock_req: MagicMock):
        """Lemonade should fallback to /v1/completions when chat fails."""
        from backend.infrastructure.llm.lemonade import LemonadeBackend

        # First call (chat) raises, second (completions) succeeds
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.json.return_value = {"choices": [{"text": "fallback response"}]}
        mock_req.side_effect = [
            requests.exceptions.RequestException("chat failed"),
            mock_resp,
        ]

        cfg = ModelConfig(
            url="http://localhost:13305/v1/chat/completions",
            model="test-model",
            timeout=10,
            backend="lemonade",
        )
        backend = LemonadeBackend(cfg)
        result = backend.generate("Hi")
        assert result == "fallback response"


# ── llama.cpp backend tests ────────────────────────────────────

class TestLlamaCppBackend:
    @patch("backend.infrastructure.llm.base.requests.request")
    def test_generate(self, mock_req: MagicMock):
        from backend.infrastructure.llm.llamacpp import LlamaCppBackend

        mock_req.return_value.json.return_value = {
            "choices": [{"message": {"content": "llama.cpp response"}}]
        }
        cfg = ModelConfig(
            url="http://localhost:8080/v1/chat/completions",
            model="test-model",
            timeout=10,
            backend="llamacpp",
        )
        backend = LlamaCppBackend(cfg)
        result = backend.generate("Hi")
        assert result == "llama.cpp response"


# ── SSE line parser tests ──────────────────────────────────────

class TestSSEParser:
    def test_normal_line(self):
        assert LLMBackend._parse_sse_line(b'data: {"key": "val"}') == '{"key": "val"}'

    def test_done_marker(self):
        assert LLMBackend._parse_sse_line(b"data: [DONE]") is None

    def test_empty_line(self):
        assert LLMBackend._parse_sse_line(b"") is None
        assert LLMBackend._parse_sse_line(b"\n") is None

    def test_no_prefix(self):
        assert LLMBackend._parse_sse_line(b'{"key": "val"}') == '{"key": "val"}'

    def test_whitespace_line(self):
        assert LLMBackend._parse_sse_line(b"  ") is None


# ── Health check tests ─────────────────────────────────────────

class TestHealthChecks:
    def test_aggregate_health_all_ok(self):
        from backend.infrastructure.llm.health import aggregate_health

        results = {
            "ollama": {"status": "ok", "latency_ms": 5.0, "error": None},
            "lmstudio": {"status": "ok", "latency_ms": 10.0, "error": None},
        }
        summary = aggregate_health(results)
        assert summary["status"] == "ok"
        assert summary["ok_count"] == 2
        assert summary["error_count"] == 0

    def test_aggregate_health_degraded(self):
        from backend.infrastructure.llm.health import aggregate_health

        results = {
            "ollama": {"status": "ok", "latency_ms": 5.0, "error": None},
            "lmstudio": {"status": "error", "latency_ms": 0, "error": "timeout"},
        }
        summary = aggregate_health(results)
        assert summary["status"] == "degraded"

    def test_aggregate_health_all_error(self):
        from backend.infrastructure.llm.health import aggregate_health

        results = {
            "ollama": {"status": "error", "latency_ms": 0, "error": "down"},
            "lmstudio": {"status": "error", "latency_ms": 0, "error": "down"},
        }
        summary = aggregate_health(results)
        assert summary["status"] == "error"
