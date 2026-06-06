"""Tests for cross-backend force_model routing in LLMWrapper.

The bug this guards against: per-node routing forces a model from one
backend (e.g. "fast" tier -> LM Studio's liquid/lfm2.5-1.2b) but
inherits user_provider (e.g. ollama) from the user's chat model
selection. The router then sends the LM Studio model name to the
Ollama backend, which 404s with LLMModelNotFoundError.

LLMWrapper now resolves force_provider from model_discovery. These
tests pin the resolution contract:

  - Cold cache OR unknown model -> fall back to user_provider.
    (Defensive: a clean 404 is better than silently misrouting.)
  - Same backend as user_provider -> no-op.
  - Different backend -> switch force_provider.
  - Explicit force_provider always wins.
  - No force_model -> keep user_provider (legacy behavior).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.domain.core.langgraph.llm_wrapper import (
    LLMWrapper,
    _resolve_provider_for_model,
)
from backend.domain.core.langgraph import nodes as langgraph_nodes


# ========================================
# Mock helpers
# ========================================


class _FakeDiscovery:
    """Stand-in for backend.infrastructure.model_discovery.ModelDiscovery.

    Configured per-test with a (model_name -> backend) map.
    """

    def __init__(self, mapping: dict[str, str] | None = None):
        self._mapping = mapping or {}

    def get_backend_for_model(self, model_name: str) -> str | None:
        if not model_name:
            return None
        return self._mapping.get(model_name)


def _patched_discovery(mapping: dict[str, str] | None):
    """Patch get_model_discovery() to return a _FakeDiscovery."""
    fake = _FakeDiscovery(mapping)

    class _Factory:
        @staticmethod
        def get_model_discovery():
            return fake

    return patch(
        "backend.infrastructure.model_discovery.get_model_discovery",
        _Factory.get_model_discovery,
    )


# ========================================
# _resolve_provider_for_model
# ========================================


class TestResolveProviderForModel:
    def test_known_model_returns_backend(self):
        with _patched_discovery({"liquid/lfm2.5-1.2b": "lmstudio"}):
            assert _resolve_provider_for_model("liquid/lfm2.5-1.2b") == "lmstudio"

    def test_unknown_model_returns_none(self):
        with _patched_discovery({"qwen3.5:9b": "ollama"}):
            assert _resolve_provider_for_model("nonexistent:99b") is None

    def test_empty_model_returns_none(self):
        with _patched_discovery({"qwen3.5:9b": "ollama"}):
            assert _resolve_provider_for_model("") is None

    def test_cold_cache_returns_none(self):
        # No mapping at all -> simulates cold cache
        with _patched_discovery(None):
            assert _resolve_provider_for_model("qwen3.5:9b") is None


# ========================================
# LLMWrapper.__init__ force_provider resolution
# ========================================


class TestForceProviderResolution:
    """The actual __init__ logic."""

    def test_explicit_force_provider_wins(self):
        """If the caller passes force_provider, never override it --
        even if the model_discovery lookup would suggest otherwise.
        Tests and explicit overrides rely on this.
        """
        with _patched_discovery({"liquid/lfm2.5-1.2b": "lmstudio"}):
            w = LLMWrapper(
                router=None,
                user_model="lfm2:latest",
                user_provider="ollama",
                force_model="liquid/lfm2.5-1.2b",
                force_provider="explicit-test",
            )
            assert w.force_provider == "explicit-test"

    def test_cross_backend_switch(self):
        """The bug fix: user on Ollama, forced model is on LM Studio.
        The wrapper must switch force_provider to lmstudio so the
        router doesn't 404 by sending the LM Studio model name to
        Ollama.
        """
        with _patched_discovery({"liquid/lfm2.5-1.2b": "lmstudio"}):
            w = LLMWrapper(
                router=None,
                user_model="lfm2:latest",
                user_provider="ollama",
                force_model="liquid/lfm2.5-1.2b",
            )
            assert w.force_provider == "lmstudio"

    def test_same_backend_no_op(self):
        """Forced model is on the same backend as user_provider ->
        no change. This is the most common case and must remain
        stable.
        """
        with _patched_discovery({"qwen3.5:9b": "ollama"}):
            w = LLMWrapper(
                router=None,
                user_model="lfm2:latest",
                user_provider="ollama",
                force_model="qwen3.5:9b",
            )
            assert w.force_provider == "ollama"

    def test_unknown_model_falls_back_to_user_provider(self):
        """If the cache is warm but doesn't have the forced model
        (e.g. it was just pulled and discovery hasn't re-run), we
        MUST NOT silently misroute. Falling back to user_provider
        yields a clean 404 from the router, which is the right
        behavior -- much better than forwarding to the wrong
        backend.
        """
        with _patched_discovery({"unrelated:7b": "ollama"}):
            w = LLMWrapper(
                router=None,
                user_model="lfm2:latest",
                user_provider="ollama",
                force_model="brand-new-model:99b",
            )
            assert w.force_provider == "ollama"

    def test_cold_cache_falls_back_to_user_provider(self):
        """If the model_discovery cache is completely cold (cache miss
        returns None), the wrapper falls back to user_provider. The
        router will then either hit (model exists on user's backend)
        or 404 cleanly (model truly missing).
        """
        with _patched_discovery(None):
            w = LLMWrapper(
                router=None,
                user_model="lfm2:latest",
                user_provider="ollama",
                force_model="liquid/lfm2.5-1.2b",
            )
            assert w.force_provider == "ollama"

    def test_no_force_model_keeps_user_provider(self):
        """Legacy behavior: when force_model is empty, every node
        uses the user's chat model on the user's backend. Must not
        regress.
        """
        with _patched_discovery({"liquid/lfm2.5-1.2b": "lmstudio"}):
            w = LLMWrapper(
                router=None,
                user_model="lfm2:latest",
                user_provider="ollama",
                force_model="",
            )
            assert w.force_provider == "ollama"
            assert w.user_model == "lfm2:latest"

    def test_lmstudio_user_to_ollama_force(self):
        """Symmetric case: user on LM Studio, forced model is on
        Ollama. Must switch the other way.
        """
        with _patched_discovery({"qwen3.5:9b": "ollama"}):
            w = LLMWrapper(
                router=None,
                user_model="liquid/lfm2.5-1.2b",
                user_provider="lmstudio",
                force_model="qwen3.5:9b",
            )
            assert w.force_provider == "ollama"

    def test_explicit_force_provider_wins_over_warm_cache(self):
        """If the caller overrides force_provider explicitly, the
        warm cache must NOT override the explicit value.
        """
        with _patched_discovery({"some-model": "auto-detected-backend"}):
            w = LLMWrapper(
                router=None,
                user_model="x",
                user_provider="ollama",
                force_model="some-model",
                force_provider="caller-override",
            )
            assert w.force_provider == "caller-override"

    def test_resolved_returns_correct_model_and_provider(self):
        """End-to-end: with a cross-backend setup, _resolved() must
        return the forced model on the switched backend.
        """
        with _patched_discovery({"liquid/lfm2.5-1.2b": "lmstudio"}):
            w = LLMWrapper(
                router=None,
                user_model="lfm2:latest",
                user_provider="ollama",
                force_model="liquid/lfm2.5-1.2b",
            )
            model, provider = w._resolved()
            assert model == "liquid/lfm2.5-1.2b"
            assert provider == "lmstudio"


# ========================================
# _force_model_for -- preset tier discovery validation
# ========================================


class _FakeSettings:
    def __init__(self, routing_on=True, preset_model="qwen3.5:9b"):
        self._routing_on = routing_on
        self._preset_model = preset_model

    def get_node_routing_enabled(self) -> bool:
        return self._routing_on

    def get_model_for_task(self, tier: str) -> str:
        return self._preset_model


class TestForceModelFor:
    def test_routing_off_returns_empty(self):
        fake = _FakeSettings(routing_on=False, preset_model="anything")
        with _patched_discovery({"qwen3.5:9b": "ollama"}):
            with patch.object(langgraph_nodes, "settings", fake):
                assert langgraph_nodes._force_model_for("fast") == ""

    def test_routing_on_model_discovered_returns_model(self):
        fake = _FakeSettings(routing_on=True, preset_model="qwen3.5:9b")
        with _patched_discovery({"qwen3.5:9b": "ollama"}):
            with patch.object(langgraph_nodes, "settings", fake):
                assert langgraph_nodes._force_model_for("fast") == "qwen3.5:9b"

    def test_routing_on_model_undiscovered_returns_empty(self):
        fake = _FakeSettings(routing_on=True, preset_model="liquid/lfm2.5-1.2b")
        with _patched_discovery({"qwen3.5:9b": "ollama"}):
            with patch.object(langgraph_nodes, "settings", fake):
                assert langgraph_nodes._force_model_for("fast") == ""

    def test_routing_on_undiscovered_logs_warning(self):
        fake = _FakeSettings(routing_on=True, preset_model="liquid/lfm2.5-1.2b")
        with _patched_discovery({"qwen3.5:9b": "ollama"}):
            with patch.object(langgraph_nodes, "settings", fake):
                with patch.object(langgraph_nodes.logger, "warning") as warn:
                    langgraph_nodes._force_model_for("fast")
        warn.assert_called_once()
        # logger.warning(format, *args) is lazy-formatted. The format
        # string stays unformatted; the actual values are in args.
        args = warn.call_args.args
        assert "fast" in args           # tier
        assert "liquid/lfm2.5-1.2b" in args  # candidate

    def test_routing_on_discovery_unavailable_keeps_candidate(self):
        """Defensive: if model_discovery itself is unavailable
        (e.g. import failure, broker crashed), the function keeps
        the preset candidate as best effort. The router will
        surface whatever error the backend produces. Better than
        silently downgrading every node to the chat model.
        """
        fake = _FakeSettings(
            routing_on=True, preset_model="liquid/lfm2.5-1.2b"
        )

        class _RaisingFactory:
            @staticmethod
            def get_model_discovery():
                raise RuntimeError("discovery module not loaded")

        with patch(
            "backend.infrastructure.model_discovery.get_model_discovery",
            _RaisingFactory.get_model_discovery,
        ):
            with patch.object(langgraph_nodes, "settings", fake):
                assert (
                    langgraph_nodes._force_model_for("fast")
                    == "liquid/lfm2.5-1.2b"
                )


    def test_routing_on_empty_preset_returns_empty(self):
        fake = _FakeSettings(routing_on=True, preset_model="")
        with _patched_discovery({"qwen3.5:9b": "ollama"}):
            with patch.object(langgraph_nodes, "settings", fake):
                assert langgraph_nodes._force_model_for("fast") == ""

    def test_routing_on_discovery_raises_keeps_candidate(self):
        fake = _FakeSettings(routing_on=True, preset_model="qwen3.5:9b")

        class _Exploding:
            def get_backend_for_model(self, name):
                raise RuntimeError("discovery broken")

        class _Factory:
            @staticmethod
            def get_model_discovery():
                return _Exploding()

        with patch("backend.infrastructure.model_discovery.get_model_discovery", _Factory.get_model_discovery):
            with patch.object(langgraph_nodes, "settings", fake):
                assert langgraph_nodes._force_model_for("fast") == "qwen3.5:9b"

    def test_cross_backend_discovered_returns_model(self):
        fake = _FakeSettings(routing_on=True, preset_model="liquid/lfm2.5-1.2b")
        with _patched_discovery({"liquid/lfm2.5-1.2b": "lmstudio"}):
            with patch.object(langgraph_nodes, "settings", fake):
                assert langgraph_nodes._force_model_for("fast") == "liquid/lfm2.5-1.2b"
