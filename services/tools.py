# services/tools.py - Tools / Function Calling
#
# Role: Tool registry and execution for function calling
# Contract:
#     async run_tool(name: str, args: dict) -> ToolResult
#     - Validates tool call against registered tools
#     - Executes with timeout (default 30s)
#     - Returns structured ToolResult

import logging
import json
import asyncio
import re
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ====================== Data Classes ======================

@dataclass
class ToolParameter:
    """Parameter definition for a tool"""
    name: str
    type: str  # "string", "number", "boolean"
    description: str
    required: bool = False


@dataclass
class Tool:
    """
    Tool definition similar to OpenAI function calling.
    """
    name: str
    description: str
    parameters: List[ToolParameter]
    handler: Optional[Callable] = None
    timeout_seconds: int = 30
    category: str = "general"

    def to_openai_schema(self) -> Dict:
        """Convert to OpenAI function calling schema"""
        properties = {}
        required_params = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description
            }
            if param.required:
                required_params.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required_params
                }
            }
        }

    def validate_arguments(self, arguments: Dict) -> tuple[bool, Optional[str]]:
        """Validate tool arguments."""
        for param in self.parameters:
            value = arguments.get(param.name)

            if param.required and value is None:
                return False, f"Missing required parameter: {param.name}"

            if value is not None:
                # Simple type check
                expected_type = param.type
                if expected_type == "number" and not isinstance(value, (int, float)):
                    return False, f"Parameter {param.name} must be a number"
                elif expected_type == "string" and not isinstance(value, str):
                    return False, f"Parameter {param.name} must be a string"
                elif expected_type == "boolean" and not isinstance(value, bool):
                    return False, f"Parameter {param.name} must be a boolean"

        return True, None

    async def execute(self, arguments: Dict) -> Dict[str, Any]:
        """Execute tool with arguments and validation"""
        try:
            is_valid, error_msg = self.validate_arguments(arguments)
            if not is_valid:
                return {"status": "error", "error": error_msg}

            if not self.handler:
                return {"status": "error", "error": "No handler defined"}

            try:
                result = await asyncio.wait_for(
                    self.handler(arguments),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                return {"status": "error", "error": f"Tool timed out after {self.timeout_seconds}s"}

            return {"status": "success", "result": result}

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"status": "error", "error": str(e)}


@dataclass
class ToolCall:
    """Represents a tool call request"""
    id: str
    name: str
    arguments: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


# ====================== Built-in Tools ======================

async def tool_calculator(arguments: Dict) -> Any:
    """Calculator tool - uses safe arithmetic parsing instead of eval()"""
    expression = arguments.get("expression", "")

    try:
        # Safe arithmetic evaluation using ast
        result = _safe_eval(expression)
        return {"expression": expression, "result": result}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Calculation error: {str(e)}"}


def _safe_eval(expr: str) -> float:
    """
    Safe arithmetic evaluation without eval().
    Supports: +, -, *, /, parentheses, and basic math functions.
    """
    expr = expr.strip()
    if not expr:
        raise ValueError("Empty expression")

    # Only allow safe characters
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expr):
        raise ValueError("Invalid characters in expression")

    # Simple recursive descent parser for basic arithmetic
    def parse_add_sub(tokens: list) -> float:
        result = parse_mul_div(tokens)
        while tokens and tokens[0] in ('+', '-'):
            op = tokens.pop(0)
            rhs = parse_mul_div(tokens)
            result = result + rhs if op == '+' else result - rhs
        return result

    def parse_mul_div(tokens: list) -> float:
        result = parse_unary(tokens)
        while tokens and tokens[0] in ('*', '/'):
            op = tokens.pop(0)
            rhs = parse_unary(tokens)
            if op == '*':
                result = result * rhs
            else:
                if rhs == 0:
                    raise ValueError("Division by zero")
                result = result / rhs
        return result

    def parse_unary(tokens: list) -> float:
        if tokens and tokens[0] == '-':
            tokens.pop(0)
            return -parse_primary(tokens)
        return parse_primary(tokens)

    def parse_primary(tokens: list) -> float:
        if not tokens:
            raise ValueError("Unexpected end of expression")

        token = tokens.pop(0)

        if token == '(':
            result = parse_add_sub(tokens)
            if tokens and tokens[0] == ')':
                tokens.pop(0)
            return result

        # Try to parse as number
        try:
            return float(token)
        except ValueError:
            raise ValueError(f"Invalid token: {token}")

    # Tokenize
    tokens = []
    current = ""
    for char in expr:
        if char in ' \t':
            if current:
                tokens.append(current)
                current = ""
        elif char in '+-*/()':
            if current:
                tokens.append(current)
                current = ""
            tokens.append(char)
        else:
            current += char
    if current:
        tokens.append(current)

    if not tokens:
        raise ValueError("Empty expression")

    return parse_add_sub(tokens)


async def tool_search_memory(arguments: Dict) -> Any:
    """Search memory tool"""
    query = arguments.get("query", "")
    k = arguments.get("k", 3)

    try:
        from .memory_service import get_memory_service
        memory = get_memory_service()
        results = memory.search(query, k=k)
        return {"query": query, "results": results}
    except Exception as e:
        return {"error": f"Memory search failed: {str(e)}"}


async def tool_get_time(arguments: Dict) -> Any:
    """Get current time tool"""
    return {"datetime": datetime.now().isoformat()}


# ====================== Tool Manager (Registry + Execution) ======================

class ToolManager:
    """
    Centralized tool management with validation and execution.
    
    Combines ToolRegistry and ToolManager - single responsibility.
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, List[str]] = {}
        self._execution_log: List[Dict] = []
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

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """List tools, optionally filtered by category"""
        if category:
            return self._categories.get(category, [])
        return list(self._tools.keys())

    def get_categories(self) -> List[str]:
        """Get all categories"""
        return list(self._categories.keys())

    def get_schemas(self) -> List[Dict]:
        """Get schemas for all tools"""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    # --- Execution Methods ---

    async def execute(
        self,
        tool_name: str,
        arguments: Dict,
        store_result: bool = False
    ) -> Dict[str, Any]:
        """Execute a tool with validation and logging"""
        start_time = datetime.now()

        tool = self.get(tool_name)
        if not tool:
            self._log_execution(tool_name, arguments, None, "error", f"Tool not found: {tool_name}")
            return {"status": "error", "error": f"Tool not found: {tool_name}"}

        # Validate
        is_valid, error_msg = tool.validate_arguments(arguments)
        if not is_valid:
            self._log_execution(tool_name, arguments, None, "validation_error", error_msg)
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
        arguments: Dict,
        result: Optional[Dict],
        status: str,
        error: Optional[str] = None
    ) -> None:
        """Log tool execution"""
        self._execution_log.append({
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "status": status,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })

        if len(self._execution_log) > self._max_log_size:
            self._execution_log = self._execution_log[-self._max_log_size:]

    def get_execution_log(self, limit: int = 10) -> List[Dict]:
        """Get recent execution log"""
        return self._execution_log[-limit:]

    def get_stats(self) -> Dict[str, Any]:
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

    def select_tool(self, task_description: str) -> Optional[str]:
        """Intelligent tool selection based on task keywords."""
        task_lower = task_description.lower()

        keyword_tools = {
            "calculate": "calculator",
            "math": "calculator",
            "remember": "search_memory",
            "search": "search_memory",
            "time": "get_time",
            "clock": "get_time",
        }

        for keyword, tool_name in keyword_tools.items():
            if keyword in task_lower and self.get(tool_name):
                return tool_name

        return None


# ====================== Singleton ======================

_tool_manager: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    """Get singleton ToolManager with built-in tools"""
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = ToolManager()

        # Register built-in tools
        _tool_manager.register(Tool(
            name="calculator",
            description="Evaluate a mathematical expression",
            parameters=[
                ToolParameter("expression", "string", "The expression to evaluate", required=True)
            ],
            handler=tool_calculator,
            category="utility",
            timeout_seconds=10
        ))

        _tool_manager.register(Tool(
            name="search_memory",
            description="Search the memory/knowledge base",
            parameters=[
                ToolParameter("query", "string", "Search query", required=True),
                ToolParameter("k", "number", "Number of results", required=False)
            ],
            handler=tool_search_memory,
            category="memory",
            timeout_seconds=30
        ))

        _tool_manager.register(Tool(
            name="get_time",
            description="Get current date and time",
            parameters=[],
            handler=tool_get_time,
            category="utility",
            timeout_seconds=5
        ))

    return _tool_manager


# ====================== Helper ======================

def create_tool(
    name: str,
    description: str,
    parameters: List[Dict],
    handler: Callable,
    category: str = "general",
    timeout_seconds: int = 30
) -> Tool:
    """Helper to create a tool from dict parameters"""
    tool_params = [
        ToolParameter(
            name=p["name"],
            type=p["type"],
            description=p["description"],
            required=p.get("required", False)
        )
        for p in parameters
    ]

    return Tool(
        name=name,
        description=description,
        parameters=tool_params,
        handler=handler,
        category=category,
        timeout_seconds=timeout_seconds
    )


__all__ = [
    "Tool",
    "ToolParameter",
    "ToolCall",
    "ToolManager",
    "get_tool_manager",
    "create_tool",
]