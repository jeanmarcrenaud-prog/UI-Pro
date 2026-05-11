# services/model_discovery.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.infrastructure.model_discovery instead

from backend.infrastructure.model_discovery import (
    ModelDiscovery,
    DiscoveredModel,
    TaskType,
    get_model_discovery,
    discover_available_models,
    is_model_available,
)

__all__ = [
    "ModelDiscovery",
    "DiscoveredModel",
    "TaskType",
    "get_model_discovery",
    "discover_available_models",
    "is_model_available",
]