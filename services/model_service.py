# services/model_service.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.infrastructure.model_service instead

from backend.infrastructure.model_service import (
    ModelPerformance,
    ModelService,
    get_model_service,
)

__all__ = [
    "ModelPerformance",
    "ModelService",
    "get_model_service",
]