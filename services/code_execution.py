# services/code_execution.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.infrastructure.code_execution instead

from backend.infrastructure.code_execution import (
    ExecutionResult,
    CodeExecutionService,
    get_code_execution_service,
    execute_code,
)

__all__ = [
    "ExecutionResult",
    "CodeExecutionService",
    "get_code_execution_service",
    "execute_code",
]