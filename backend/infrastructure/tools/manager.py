# backend/infrastructure/tools/manager.py
# Role: ToolManager registry, execution, and singleton factory

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .models import Tool, ToolParameter
from .builtins import tool_calculator, tool_get_time

logger = logging.getLogger(__name__)


class ToolManager:
    """
    Centralized tool management with validation and execution.

    Combines ToolRegistry and ToolManager - single responsibility.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._categories: dict[str, list[str]] = {}
        self._execution_log: list[dict] = []
        self._max_log_size = 100

    # --- Registry Methods ---

    def register(self, tool: Tool) -> None:
        """Register a tool"""
        self._tools[tool.name] = tool

        category = tool.category or "general"
        if category not in self._categories:
            self._categories[category] = []
        if tool.name not in self._categories[category]:
            self._categories[category].append(tool.name)

        logger.info(f"Registered tool: {tool.name}")

    def unregister(self, name: str) -> bool:
        """Unregister a tool"""
        if name in self._tools:
            del self._tools[name]
            for cat_tools in self._categories.values():
                if name in cat_tools:
                    cat_tools.remove(name)
            return True
        return False

    def get(self, name: str) -> Tool | None:
        """Get a tool by name"""
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[str]:
        """List tools, optionally filtered by category"""
        if category:
            return self._categories.get(category, [])
        return list(self._tools.keys())

    def get_categories(self) -> list[str]:
        """Get all categories"""
        return list(self._categories.keys())

    def get_schemas(self) -> list[dict]:
        """Get schemas for all tools"""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    # --- Execution Methods ---

    async def execute(
        self, tool_name: str, arguments: dict, store_result: bool = False
    ) -> dict[str, Any]:
        """Execute a tool with validation and logging"""
        start_time = datetime.now()

        tool = self.get(tool_name)
        if not tool:
            self._log_execution(
                tool_name, arguments, None, "error", f"Tool not found: {tool_name}"
            )
            return {"status": "error", "error": f"Tool not found: {tool_name}"}

        # Validate
        is_valid, error_msg = tool.validate_arguments(arguments)
        if not is_valid:
            self._log_execution(
                tool_name, arguments, None, "validation_error", error_msg
            )
            return {"status": "error", "error": error_msg}

        # Execute
        try:
            result = await tool.execute(arguments)
            status = result.get("status", "unknown")
            self._log_execution(tool_name, arguments, result, status)
            return result

        except Exception as e:
            error_msg = str(e)
            self._log_execution(tool_name, arguments, None, "error", error_msg)
            return {"status": "error", "error": error_msg}

    def _log_execution(
        self,
        tool_name: str,
        arguments: dict,
        result: dict | None,
        status: str,
        error: str | None = None,
    ) -> None:
        """Log tool execution"""
        self._execution_log.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "status": status,
                "error": error,
                "timestamp": datetime.now().isoformat(),
            }
        )

        if len(self._execution_log) > self._max_log_size:
            self._execution_log = self._execution_log[-self._max_log_size :]

    def get_execution_log(self, limit: int = 10) -> list[dict]:
        """Get recent execution log"""
        return self._execution_log[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get tool usage statistics"""
        stats = {}
        for entry in self._execution_log:
            tool_name = entry["tool_name"]
            if tool_name not in stats:
                stats[tool_name] = {"total": 0, "success": 0, "error": 0}

            stats[tool_name]["total"] += 1
            if entry["status"] == "success":
                stats[tool_name]["success"] += 1
            else:
                stats[tool_name]["error"] += 1

        return stats

    def select_tool(self, task_description: str) -> str | None:
        """Intelligent tool selection based on task keywords."""
        task_lower = task_description.lower()

        keyword_tools = {
            "calculate": "calculator",
            "math": "calculator",
            "time": "get_time",
            "clock": "get_time",
        }

        for keyword, tool_name in keyword_tools.items():
            if keyword in task_lower and self.get(tool_name):
                return tool_name

        return None


# ====================== Singleton ======================

_tool_manager: ToolManager | None = None


def get_tool_manager() -> ToolManager:
    """Get singleton ToolManager with built-in tools"""
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = ToolManager()

        # Register built-in tools
        _tool_manager.register(
            Tool(
                name="calculator",
                description="Evaluate a mathematical expression",
                parameters=[
                    ToolParameter(
                        "expression",
                        "string",
                        "The expression to evaluate",
                        required=True,
                    )
                ],
                handler=tool_calculator,
                category="utility",
                timeout_seconds=10,
            )
        )

        _tool_manager.register(
            Tool(
                name="get_time",
                description="Get current date and time",
                parameters=[],
                handler=tool_get_time,
                category="utility",
                timeout_seconds=5,
            )
        )

    return _tool_manager


# ====================== Helper ======================


def create_tool(
    name: str,
    description: str,
    parameters: list[dict],
    handler: Callable,
    category: str = "general",
    timeout_seconds: int = 30,
) -> Tool:
    """Helper to create a tool from dict parameters"""
    tool_params = [
        ToolParameter(
            name=p["name"],
            type=p["type"],
            description=p["description"],
            required=p.get("required", False),
        )
        for p in parameters
    ]

    return Tool(
        name=name,
        description=description,
        parameters=tool_params,
        handler=handler,
        category=category,
        timeout_seconds=timeout_seconds,
    )
