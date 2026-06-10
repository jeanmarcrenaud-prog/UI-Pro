"""
Prometheus metrics for pipeline orchestration, sessions, and checkpoints.

Exposes:
  - orchestrator_active_sessions     — Gauge: in-flight pipeline runs
  - orchestrator_pipeline_runs_total  — Counter: completed runs by status
  - checkpoint_saves_total            — Counter: stream checkpoint saves
  - node_execution_duration_seconds   — Histogram: per-node execution time

Usage:
    from backend.infrastructure.monitoring.pipeline_metrics import (
        inc_active_sessions,
        dec_active_sessions,
        inc_pipeline_run,
        inc_checkpoint_save,
        observe_node_duration,
    )
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy-init
_registry: Any = None
_gauge_sessions: Any = None
_counter_runs: Any = None
_counter_checkpoints: Any = None
_histogram_node: Any = None


def _ensure():
    """Lazy-import prometheus_client and build metrics."""
    global _registry, _gauge_sessions, _counter_runs
    global _counter_checkpoints, _histogram_node
    if _gauge_sessions is not None:
        return True

    try:
        import prometheus_client  # type: ignore[import-untyped]
    except ImportError:
        return False

    if _registry is None:
        from backend.infrastructure.monitoring.prometheus import get_metrics_registry

        _registry = get_metrics_registry()

    _gauge_sessions = prometheus_client.Gauge(
        "orchestrator_active_sessions",
        "Currently active pipeline runs",
        registry=_registry,
    )
    _counter_runs = prometheus_client.Counter(
        "orchestrator_pipeline_runs_total",
        "Total pipeline runs by status",
        labelnames=["status"],
        registry=_registry,
    )
    _counter_checkpoints = prometheus_client.Counter(
        "checkpoint_saves_total",
        "Total stream checkpoint saves",
        registry=_registry,
    )
    _histogram_node = prometheus_client.Histogram(
        "node_execution_duration_seconds",
        "Per-node execution duration",
        labelnames=["node_name"],
        buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
        registry=_registry,
    )
    return True


def inc_active_sessions() -> None:
    """Increment the active sessions gauge."""
    if not _ensure():
        return
    try:
        _gauge_sessions.inc()
    except Exception:
        pass


def dec_active_sessions() -> None:
    """Decrement the active sessions gauge."""
    if not _ensure():
        return
    try:
        _gauge_sessions.dec()
    except Exception:
        pass


def inc_pipeline_run(status: str = "success") -> None:
    """Increment the pipeline run counter by status."""
    if not _ensure():
        return
    try:
        _counter_runs.labels(status=status).inc()
    except Exception:
        pass


def inc_checkpoint_save() -> None:
    """Increment the checkpoint counter."""
    if not _ensure():
        return
    try:
        _counter_checkpoints.inc()
    except Exception:
        pass


def observe_node_duration(node_name: str, duration_s: float) -> None:
    """Record a node execution duration."""
    if not _ensure():
        return
    try:
        _histogram_node.labels(node_name=node_name).observe(duration_s)
    except Exception:
        pass
