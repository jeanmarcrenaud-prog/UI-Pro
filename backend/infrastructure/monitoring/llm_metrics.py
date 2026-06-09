"""
Prometheus metrics for LLM request latency, token throughput, and error rates.

Exposes:
  - llm_request_latency_seconds   — Histogram: request duration
  - llm_errors_total              — Counter: failed requests by provider
  - llm_active_requests           — Gauge: in-flight requests
  - llm_tokens_total              — Counter: generated tokens by provider

Usage:
    from backend.infrastructure.monitoring.llm_metrics import (
        observe_llm_latency,
        inc_llm_error,
        set_active_requests,
        inc_llm_tokens,
    )

    # In llm_wrapper:
    inc_llm_tokens(provider, count)
    observe_llm_latency(provider, duration_seconds)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy-init
_registry: Any = None
_histogram: Any = None
_error_counter: Any = None
_active_gauge: Any = None
_token_counter: Any = None


def _ensure():
    """Lazy-import prometheus_client and build metrics."""
    global _registry, _histogram, _error_counter, _active_gauge, _token_counter
    if _histogram is not None:
        return True

    try:
        import prometheus_client  # type: ignore[import-untyped]
    except ImportError:
        return False

    if _registry is None:
        from backend.infrastructure.monitoring.prometheus import get_metrics_registry

        _registry = get_metrics_registry()

    _histogram = prometheus_client.Histogram(
        "llm_request_latency_seconds",
        "LLM request latency in seconds",
        buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600),
        labelnames=["provider", "model_type"],
        registry=_registry,
    )
    _error_counter = prometheus_client.Counter(
        "llm_errors_total",
        "Total LLM errors by provider",
        labelnames=["provider", "error_type"],
        registry=_registry,
    )
    _active_gauge = prometheus_client.Gauge(
        "llm_active_requests",
        "Currently in-flight LLM requests",
        labelnames=["provider"],
        registry=_registry,
    )
    _token_counter = prometheus_client.Counter(
        "llm_tokens_total",
        "Total generated tokens by provider",
        labelnames=["provider"],
        registry=_registry,
    )
    return True


def observe_llm_latency(provider: str, duration_s: float, model_type: str = "fast") -> None:
    """Record an LLM request latency observation."""
    if not _ensure():
        return
    try:
        _histogram.labels(provider=provider, model_type=model_type).observe(duration_s)
    except Exception:
        pass


def inc_llm_error(provider: str, error_type: str = "unknown") -> None:
    """Increment the error counter for a provider."""
    if not _ensure():
        return
    try:
        _error_counter.labels(provider=provider, error_type=error_type).inc()
    except Exception:
        pass


def set_active_requests(provider: str, count: int) -> None:
    """Set the gauge for in-flight requests."""
    if not _ensure():
        return
    try:
        _active_gauge.labels(provider=provider).set(count)
    except Exception:
        pass


def inc_llm_tokens(provider: str, count: int = 1) -> None:
    """Increment the generated token counter."""
    if not _ensure():
        return
    try:
        _token_counter.labels(provider=provider).inc(count)
    except Exception:
        pass
