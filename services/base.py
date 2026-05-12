# services/base.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.infrastructure.base instead

from backend.infrastructure.base import (
    BaseService,
    ServiceMetrics,
)

__all__ = [
    "BaseService",
    "ServiceMetrics",
]