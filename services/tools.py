# services/tools.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.infrastructure.tools instead

from backend.infrastructure.tools import (
    ToolParameter,
    Tool,
    ToolCall,
    ToolManager,
    get_tool_manager,
    create_tool,
)

__all__ = [
    "ToolParameter",
    "Tool",
    "ToolCall",
    "ToolManager",
    "get_tool_manager",
    "create_tool",
]