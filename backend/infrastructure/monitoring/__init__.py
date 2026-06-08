"""Monitoring — Prometheus metrics for GPU, system, and LLM telemetry."""

from backend.infrastructure.monitoring.prometheus import (
    PROMETHEUS_ENABLED,
    get_metrics_registry,
    update_system_metrics,
    METRIC_GPU_UTILIZATION,
    METRIC_GPU_MEMORY_USED,
    METRIC_GPU_MEMORY_TOTAL,
    METRIC_GPU_TEMPERATURE,
    METRIC_CPU_PERCENT,
    METRIC_MEMORY_PERCENT,
)
from backend.infrastructure.monitoring.llm_metrics import (
    observe_llm_latency,
    inc_llm_error,
    set_active_requests,
    inc_llm_tokens,
)

__all__ = [
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
