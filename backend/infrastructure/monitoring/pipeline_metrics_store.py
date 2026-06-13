"""
In-memory rolling store for per-node pipeline metrics.

Captures the last N observations (duration, token count) per node so the
frontend can query p50/p95/p99 latency and aggregate token usage without
a Prometheus server.  Populated by ``@_timed_node`` in ``nodes.py``.

Usage::

    from backend.infrastructure.monitoring.pipeline_metrics_store import (
        observe_node,
        get_all_node_metrics,
        get_node_metrics,
        reset_node_metrics,
    )

    observe_node("analyzing", 2.34, tokens=512)
    all_metrics = get_all_node_metrics()
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

MAX_OBSERVATIONS_PER_NODE = 100


# ── Percentile helper ──────────────────────────────────────────────────


def _percentile(sorted_data: list[float], p: float) -> float:
    """Linear-interpolated percentile from a *sorted* list."""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    k = (n - 1) * p / 100.0
    f = int(k)
    c = f + 1
    if c >= n:
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


# ── Store ──────────────────────────────────────────────────────────────


class _NodeMetricsStore:
    """Rolling window store.  Thread-unsafe by design — LangGraph nodes run
    sequentially, so there is no concurrent access to worry about."""

    def __init__(self, max_obs: int = MAX_OBSERVATIONS_PER_NODE) -> None:
        self._max = max_obs
        self._durations: dict[str, list[float]] = defaultdict(list)
        self._token_counts: dict[str, list[int]] = defaultdict(list)

    def observe(self, node_name: str, duration_s: float, tokens: int = 0) -> None:
        dur = self._durations[node_name]
        dur.append(duration_s)
        if len(dur) > self._max:
            dur.pop(0)

        if tokens > 0:
            tc = self._token_counts[node_name]
            tc.append(tokens)
            if len(tc) > self._max:
                tc.pop(0)

    def get_node_metrics(self, node_name: str) -> dict[str, Any]:
        durations = self._durations.get(node_name, [])
        tokens = self._token_counts.get(node_name, [])

        if not durations:
            return {"duration": {"count": 0}, "tokens": {"count": 0}}

        sorted_d = sorted(durations)

        return {
            "duration": {
                "count": len(sorted_d),
                "last": sorted_d[-1],
                "avg": sum(sorted_d) / len(sorted_d),
                "min": sorted_d[0],
                "max": sorted_d[-1],
                "p50": _percentile(sorted_d, 50),
                "p95": _percentile(sorted_d, 95),
                "p99": _percentile(sorted_d, 99),
            },
            "tokens": {
                "count": len(tokens),
                "last": tokens[-1] if tokens else 0,
                "avg": sum(tokens) / len(tokens) if tokens else 0,
                "total": sum(tokens),
            },
        }

    def get_all_metrics(self) -> dict[str, Any]:
        return {
            "nodes": {
                name: self.get_node_metrics(name)
                for name in sorted(self._durations.keys())
            }
        }

    def reset(self) -> None:
        self._durations.clear()
        self._token_counts.clear()


# ── Singleton ──────────────────────────────────────────────────────────

_store = _NodeMetricsStore()


def observe_node(node_name: str, duration_s: float, tokens: int = 0) -> None:
    _store.observe(node_name, duration_s, tokens)


def get_node_metrics(node_name: str) -> dict[str, Any]:
    return _store.get_node_metrics(node_name)


def get_all_node_metrics() -> dict[str, Any]:
    return _store.get_all_metrics()


def reset_node_metrics() -> None:
    _store.reset()
