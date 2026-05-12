# services/service_api.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.infrastructure.service_api instead

from backend.infrastructure.service_api import (
    ServiceAPI,
    get_service_api,
    get_streaming,
    get_model,
    get_memory,
)

__all__ = [
    "ServiceAPI",
    "get_service_api",
    "get_streaming",
    "get_model",
    "get_memory",
]