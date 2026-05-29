"""Tests for the auto-fallback between LLM backends.

All tests use mocked HTTP responses — no real backends required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.llm.models import ModelConfig
from backend.infrastructure.llm.errors import LLMBackendError, LLMConnectionError
from backend.infrastructure.llm.fallback import (
    _fallback_order,
    generate_with_fallback,
    stream_with_fallback,
)


class TestFallbackOrder:
    def test_ollama_primary(self):
        assert _fallback_order("ollama") == [
            "ollama",
            "lmstudio",
            "lemonade",
            "llamacpp",
        ]

    def test_lmstudio_primary(self):
        assert _fallback_order("lmstudio") == [
            "lmstudio",
            "ollama",
            "lemonade",
            "llamacpp",
        ]

    def test_unknown_primary(self):
        order = _fallback_order("unknown")
        assert order[0] == "unknown"
        assert len(order) == 5  # unknown + 4 known


class TestGenerateWithFallback:
    @patch("backend.infrastructure.llm.fallback.get_backend")
    def test_primary_succeeds(self, mock_get: MagicMock):
        """Primary backend succeeds — no fallback needed."""
        mock_backend = MagicMock()
        mock_backend.generate.return_value = "Hello from primary"
        mock_get.return_value = mock_backend

        result = generate_with_fallback(
            "Hi", provider="ollama", model="test-model", fallback=False
        )
        assert result == "Hello from primary"
        assert mock_get.call_count == 1

    @patch("backend.infrastructure.llm.fallback.get_backend")
    def test_fallback_on_connection_error(self, mock_get: MagicMock):
        """Primary fails with connection error, fallback succeeds."""
        primary = MagicMock()
        primary.generate.side_effect = LLMConnectionError("Ollama down")

        fallback = MagicMock()
        fallback.generate.return_value = "Fallback response"

        mock_get.side_effect = [primary, fallback]

        result = generate_with_fallback(
            "Hi", provider="ollama", model="test-model", fallback=True
        )
        assert result == "Fallback response"
        assert mock_get.call_count == 2

    @patch("backend.infrastructure.llm.fallback.get_backend")
    def test_all_backends_fail(self, mock_get: MagicMock):
        """All backends fail — should raise LLMBackendError."""
        failing = MagicMock()
        failing.generate.side_effect = LLMConnectionError("Down")

        mock_get.return_value = failing

        with pytest.raises(LLMBackendError, match="All backends failed"):
            generate_with_fallback(
                "Hi", provider="ollama", model="test-model", fallback=True
            )

    @patch("backend.infrastructure.llm.fallback.get_backend")
    def test_no_fallback_disabled(self, mock_get: MagicMock):
        """fallback=False — should only try primary, then raise."""
        failing = MagicMock()
        failing.generate.side_effect = LLMConnectionError("Down")
        mock_get.return_value = failing

        with pytest.raises(LLMBackendError, match="All backends failed"):
            generate_with_fallback(
                "Hi", provider="ollama", model="test-model", fallback=False
            )
        assert mock_get.call_count == 1  # Only tried primary


class TestStreamWithFallback:
    @patch("backend.infrastructure.llm.fallback.get_backend")
    def test_primary_succeeds(self, mock_get: MagicMock):
        mock_backend = MagicMock()
        mock_backend.stream.return_value = iter(["Hello", " world"])
        mock_get.return_value = mock_backend

        tokens = list(
            stream_with_fallback(
                "Hi", provider="ollama", model="test-model", fallback=False
            )
        )
        assert tokens == ["Hello", " world"]

    @patch("backend.infrastructure.llm.fallback.get_backend")
    def test_fallback_on_connection_error(self, mock_get: MagicMock):
        primary = MagicMock()
        primary.stream.side_effect = LLMConnectionError("Ollama down")

        fallback = MagicMock()
        fallback.stream.return_value = iter(["fallback ", "response"])

        mock_get.side_effect = [primary, fallback]

        tokens = list(
            stream_with_fallback(
                "Hi", provider="ollama", model="test-model", fallback=True
            )
        )
        assert tokens == ["fallback ", "response"]

    @patch("backend.infrastructure.llm.fallback.get_backend")
    def test_all_backends_fail(self, mock_get: MagicMock):
        failing = MagicMock()
        failing.stream.side_effect = LLMConnectionError("Down")
        mock_get.return_value = failing

        with pytest.raises(LLMBackendError, match="All backends failed for streaming"):
            list(
                stream_with_fallback(
                    "Hi", provider="ollama", model="test-model", fallback=True
                )
            )
