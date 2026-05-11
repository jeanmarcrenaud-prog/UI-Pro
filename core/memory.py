# core/memory.py - Backward Compatibility Re-export

# MemoryManager, get_memory_manager, add_memory, search_memory, model, MemoryManager
from backend.infrastructure.memory import (
    MemoryManager,
    get_memory_manager,
    add_memory,
    search_memory,
    MockLogger,
)

try:
    from backend.infrastructure.memory import model as _memory_model
    model = _memory_model
except ImportError:
    model = None

__all__ = ["MemoryManager", "get_memory_manager", "add_memory", "search_memory", "MockLogger", "model"]
