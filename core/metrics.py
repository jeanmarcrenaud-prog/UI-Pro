# core/metrics.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.domain.core.metrics instead

from backend.domain.core.metrics import (
    ExecutionRecord,
    Metrics,
    MetricsManager,
    get_metrics_manager,
    record_execution,
    get_metrics,
    get_dashboard_data,
)

__all__ = [
    "ExecutionRecord",
    "Metrics",
    "MetricsManager",
    "get_metrics_manager",
    "record_execution",
    "get_metrics",
    "get_dashboard_data",
]