# core/logger.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.domain.core.logger instead

from backend.domain.core.logger import (
    JSONFormatter,
    LoggerManager,
    set_correlation_id,
    get_correlation_id,
    generate_correlation_id,
    get_logger,
    debug,
    info,
    warning,
    error,
    critical,
    log_performance,
)

__all__ = [
    "JSONFormatter",
    "LoggerManager",
    "set_correlation_id",
    "get_correlation_id",
    "generate_correlation_id",
    "get_logger",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "log_performance",
]