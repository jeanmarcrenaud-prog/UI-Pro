# core/executor.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.domain.core.executor instead

from backend.domain.core.executor import (
    CodeExecutor,
    ExecutionConfig,
)

__all__ = [
    "CodeExecutor",
    "ExecutionConfig",
]