# services/llm_router.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.infrastructure.llm_router instead

from backend.infrastructure.llm_router import (
    TaskType,
    RouterConfig,
    LLMRouter,
    get_llm_router,
)

__all__ = [
    "TaskType",
    "RouterConfig",
    "LLMRouter",
    "get_llm_router",
]