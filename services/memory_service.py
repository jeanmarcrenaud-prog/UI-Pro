# services/memory_service.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.infrastructure.memory_service instead

from backend.infrastructure.memory_service import (
    MemoryEntry,
    ContextBuilder,
    MemoryService,
    get_memory_service,
)

__all__ = [
    "MemoryEntry",
    "ContextBuilder",
    "MemoryService",
    "get_memory_service",
]