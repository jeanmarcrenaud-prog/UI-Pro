# services/error_handler.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.infrastructure.error_handler instead

from backend.infrastructure.error_handler import (
    ErrorCategory,
    ErrorDetails,
    ErrorMetrics,
    ErrorHandler,
    get_error_handler,
)

__all__ = [
    "ErrorCategory",
    "ErrorDetails",
    "ErrorMetrics",
    "ErrorHandler",
    "get_error_handler",
]