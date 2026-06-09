"""Tests for the Prometheus monitoring module.

Covers:
- Module import and PROMETHEUS_ENABLED state
- Graceful fallback when prometheus_client is not installed
- generate_metrics_response() fallback output
- LLM metrics no-op safety without prometheus_client
"""

from __future__ import annotations

import importlib

import pytest


# =============================================================================
# Helpers
# =============================================================================


def _reload_monitoring():
    """Force-reload the monitoring modules to reset lazy-init state."""
    for mod in list(
        sorted(
            k
            for k in list(importlib.import_module("sys").modules)
            if "monitoring" in k
        )
    ):
        importlib.import_module("sys").modules.pop(mod, None)


# =============================================================================
# PROMETHEUS_ENABLED
# =============================================================================


class TestPrometheusEnabled:
    """PROMETHEUS_ENABLED module-level boolean."""

    def test_is_bool(self):
        """PROMETHEUS_ENABLED should be a plain bool, not a property object."""
        from backend.infrastructure.monitoring.prometheus import PROMETHEUS_ENABLED

        assert isinstance(PROMETHEUS_ENABLED, bool)

    def test_defaults_false_without_client(self):
        """Without prometheus_client, PROMETHEUS_ENABLED stays False."""
        _reload_monitoring()
        # Simulate missing prometheus_client for this import
        import builtins

        real_import = builtins.__import__

        def _mock_import(name, *args, **kwargs):
            if name == "prometheus_client":
                raise ImportError("Not installed")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = _mock_import
        try:
            from backend.infrastructure.monitoring.prometheus import (
                PROMETHEUS_ENABLED,
                _ensure_registry,
            )

            _ensure_registry()
            assert PROMETHEUS_ENABLED is False
        finally:
            builtins.__import__ = real_import
            _reload_monitoring()


# =============================================================================
# generate_metrics_response
# =============================================================================


class TestGenerateMetricsResponse:
    """generate_metrics_response() output."""

    @pytest.mark.asyncio
    async def test_returns_valid_prometheus_output(self):
        """With prometheus_client installed, returns valid Prometheus text."""
        # Force re-init so registry is fresh
        from backend.infrastructure.monitoring.prometheus import (
            get_metrics_registry,
        )

        registry = get_metrics_registry()
        assert registry is not None  # prometheus_client is installed

        from backend.infrastructure.monitoring.prometheus import (
            generate_metrics_response,
        )

        body, status, headers = await generate_metrics_response()
        assert status == 200
        assert body.startswith("# HELP")
        assert "gpu_utilization_percent" in body
        assert "cpu_percent" in body
        assert "memory_percent" in body
        assert "content-type" in headers
        assert "text/plain" in headers.get("content-type", "")


# =============================================================================
# LLM metrics — no-op safety
# =============================================================================


class TestLlmMetricsNoop:
    """LLM metric functions should be safe to call without prometheus_client."""

    def test_observe_llm_latency_noop(self):
        from backend.infrastructure.monitoring.llm_metrics import (
            observe_llm_latency,
        )

        # Should not raise
        observe_llm_latency("test_provider", 1.0, "fast")

    def test_inc_llm_error_noop(self):
        from backend.infrastructure.monitoring.llm_metrics import inc_llm_error

        inc_llm_error("test_provider", "timeout")

    def test_set_active_requests_noop(self):
        from backend.infrastructure.monitoring.llm_metrics import (
            set_active_requests,
        )

        set_active_requests("test_provider", 1)

    def test_inc_llm_tokens_noop(self):
        from backend.infrastructure.monitoring.llm_metrics import inc_llm_tokens

        inc_llm_tokens("test_provider", 42)

    def test_all_functions_noop_with_labels(self):
        """All label combinations should be safe."""
        from backend.infrastructure.monitoring.llm_metrics import (
            inc_llm_error,
            inc_llm_tokens,
            observe_llm_latency,
            set_active_requests,
        )

        observe_llm_latency("ollama", 2.5, "reasoning")
        inc_llm_error("lmstudio", "stream_error")
        set_active_requests("openai-compat", 3)
        inc_llm_tokens("ollama", 128)


# =============================================================================
# update_system_metrics — no-op safety
# =============================================================================


class TestSystemMetricsNoop:
    """update_system_metrics() should be safe without psutil/pynvml."""

    def test_update_system_metrics_noop(self):
        from backend.infrastructure.monitoring.prometheus import (
            update_system_metrics,
        )

        # Should not raise even without psutil and pynvml
        update_system_metrics()


# =============================================================================
# __init__.py exports
# =============================================================================


class TestInitExports:
    """The monitoring __init__.py should export expected names."""

    def test_all_exported_names_exist(self):
        import backend.infrastructure.monitoring as m

        expected = [
            "PROMETHEUS_ENABLED",
            "get_metrics_registry",
            "update_system_metrics",
            "METRIC_GPU_UTILIZATION",
            "METRIC_GPU_MEMORY_USED",
            "METRIC_GPU_MEMORY_TOTAL",
            "METRIC_GPU_TEMPERATURE",
            "METRIC_CPU_PERCENT",
            "METRIC_MEMORY_PERCENT",
            "observe_llm_latency",
            "inc_llm_error",
            "set_active_requests",
            "inc_llm_tokens",
        ]
        for name in expected:
            assert hasattr(m, name), f"{name} missing from monitoring __init__"
