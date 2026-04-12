# services/tools.py - Tools / Function Calling
"""
ToolManager - Validate, execute and log tool calls.

Contract:
    async run_tool(name: str, args: dict) -> ToolResult
    
    - Validates tool call against registered tools
    - Executes with timeout (default 30s)
    - Returns structured ToolResult
    
Registered tools:
    - calculator
    - search_memory
    - get_time
    
Dependencies:
    - core/executor.py for sandboxed code execution
"""

import logging
import json
import asyncio
from typing import Optional, Dict, Any, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ToolResultStatus(Enum):
    """Tool execution result status"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


@dataclass
class ToolParameter:
    """Parameter definition for a tool"""
    name: str
    type: str  # "string", "number", "boolean", "object", "array"
    description: str
    required: bool = False
    enum: Optional[List[str]] = None
    # Validation
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern


@dataclass
class Tool:
    """
    Tool definition similar to OpenAI function calling.
    
    Attributes:
        name: Tool name
        description: What the tool does
        parameters: List of parameter definitions
        handler: Async function to execute
    """
    name: str
    description: str
    parameters: List[ToolParameter]
    handler: Optional[Callable] = None
    
    # For synchronous handlers
    sync_handler: Optional[Callable] = None
    
    # Security settings
    timeout_seconds: int = 30
    requires_sandbox: bool = False
    allowed_categories: Optional[List[str]] = None  # For code execution
    
    # Metadata
    category: str = "general"
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    
    def to_openai_schema(self) -> Dict:
        """Convert to OpenAI function calling schema"""
        properties = {}
        required_params = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            
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
        """
        Validate tool arguments.
        
        Returns:
            (is_valid, error_message)
        """
        for param in self.parameters:
            value = arguments.get(param.name)
            
            # Check required
            if param.required and value is None:
                return False, f"Missing required parameter: {param.name}"
            
            if value is not None:
                # Type check
                expected_type = param.type
                if expected_type == "number" and not isinstance(value, (int, float)):
                    return False, f"Parameter {param.name} must be a number"
                elif expected_type == "string" and not isinstance(value, str):
                    return False, f"Parameter {param.name} must be a string"
                elif expected_type == "boolean" and not isinstance(value, bool):
                    return False, f"Parameter {param.name} must be a boolean"
                
                # Value constraints
                if param.min_value is not None and isinstance(value, (int, float)):
                    if value < param.min_value:
                        return False, f"Parameter {param.name} must be >= {param.min_value}"
                
                if param.max_value is not None and isinstance(value, (int, float)):
                    if value > param.max_value:
                        return False, f"Parameter {param.name} must be <= {param.max_value}"
                
                if param.max_length is not None and isinstance(value, str):
                    if len(value) > param.max_length:
                        return False, f"Parameter {param.name} must be <= {param.max_length} chars"
                
                if param.pattern is not None and isinstance(value, str):
                    import re
                    if not re.match(param.pattern, value):
                        return False, f"Parameter {param.name} doesn't match required pattern"
        
        return True, None
    
    async def execute(self, arguments: Dict) -> Dict[str, Any]:
        """Execute tool with arguments and validation"""
        try:
            # Validate arguments
            is_valid, error_msg = self.validate_arguments(arguments)
            if not is_valid:
                return {
                    "status": "error",
                    "error": error_msg
                }
            
            # Execute with timeout
            try:
                if self.handler:
                    result = await asyncio.wait_for(
                        self.handler(arguments),
                        timeout=self.timeout_seconds
                    )
                elif self.sync_handler:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: self.sync_handler(arguments)),
                        timeout=self.timeout_seconds
                    )
                else:
                    return {
                        "status": "error",
                        "error": "No handler defined"
                    }
            except asyncio.TimeoutError:
                return {
                    "status": "error",
                    "error": f"Tool execution timed out after {self.timeout_seconds}s"
                }
            
            return {
                "status": "success",
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


@dataclass
class ToolCall:
    """Represents a tool call request"""
    id: str
    name: str
    arguments: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class ToolRegistry:
    """
    Registry for managing tools.
    
    Features:
    - Register/unregister tools
    - Tool discovery
    - Schema generation for LLM
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool"""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all tool names"""
        return list(self._tools.keys())
    
    def get_schemas(self) -> List[Dict]:
        """Get OpenAI-compatible schemas for all tools"""
        return [tool.to_openai_schema() for tool in self._tools.values()]
    
    async def execute_call(self, tool_call: ToolCall) -> Dict[str, Any]:
        """Execute a tool call"""
        tool = self.get(tool_call.name)
        
        if not tool:
            return {
                "status": "error",
                "error": f"Tool not found: {tool_call.name}"
            }
        
        return await tool.execute(tool_call.arguments)


# Built-in tools

async def tool_calculator(arguments: Dict) -> Any:
    """Simple calculator tool"""
    expression = arguments.get("expression", "")
    try:
        # Safe eval (basic)
        allowed = set("0123456789+-*/.() ")
        if all(c in allowed for c in expression):
            result = eval(expression)
            return {"expression": expression, "result": result}
        return {"error": "Invalid expression"}
    except Exception as e:
        return {"error": str(e)}


async def tool_search_memory(arguments: Dict) -> Any:
    """Search memory tool"""
    query = arguments.get("query", "")
    k = arguments.get("k", 3)
    
    from .memory_service import get_memory_service
    memory = get_memory_service()
    results = memory.search(query, k=k)
    
    return {"query": query, "results": results}


async def tool_get_time(arguments: Dict) -> Any:
    """Get current time tool"""
    from datetime import datetime
    return {"datetime": datetime.now().isoformat()}


# Create default registry with built-in tools
_default_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get singleton tool registry with default tools"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
        
        # Register built-in tools
        _default_registry.register(Tool(
            name="calculator",
            description="Evaluate a mathematical expression",
            parameters=[
                ToolParameter("expression", "string", "The expression to evaluate", required=True)
            ],
            handler=tool_calculator
        ))
        
        _default_registry.register(Tool(
            name="search_memory",
            description="Search the memory/knowledge base",
            parameters=[
                ToolParameter("query", "string", "Search query", required=True),
                ToolParameter("k", "number", "Number of results", required=False)
            ],
            handler=tool_search_memory
        ))
        
        _default_registry.register(Tool(
            name="get_time",
            description="Get current date and time",
            parameters=[],
            handler=tool_get_time
        ))
    
    return _default_registry


# Helper to create custom tool
def create_tool(
    name: str,
    description: str,
    parameters: List[Dict],
    handler: Callable
) -> Tool:
    """Helper to create a tool from dict parameters"""
    tool_params = [
        ToolParameter(
            name=p["name"],
            type=p["type"],
            description=p["description"],
            required=p.get("required", False),
            enum=p.get("enum")
        )
        for p in parameters
    ]
    
    return Tool(
        name=name,
        description=description,
        parameters=tool_params,
        handler=handler
    )


__all__ = [
    "Tool",
    "ToolParameter",
    "ToolCall",
    "ToolRegistry",
    "ToolResultStatus",
    "get_tool_registry",
    "create_tool",
    "ToolManager"
]


class ToolManager:
    """
    Centralized tool management with validation and security.
    
    Features:
    - Tool categorization
    - Execution logging
    - Memory integration
    - Tool selection intelligence
    - Rate limiting (future)
    """
    
    def __init__(self):
        self._registry = ToolRegistry()
        self._categories: Dict[str, List[str]] = {}  # category -> tool names
        self._execution_log: List[Dict] = []
        self._max_log_size = 100
        self._memory_service = None
    
    def register(self, tool: Tool) -> None:
        """Register a tool"""
        self._registry.register(tool)
        
        # Add to category
        category = tool.category or "general"
        if category not in self._categories:
            self._categories[category] = []
        if tool.name not in self._categories[category]:
            self._categories[category].append(tool.name)
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool"""
        return self._registry.unregister(name)
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._registry.get(name)
    
    def list_tools(self, category: str = None) -> List[str]:
        """List tools, optionally filtered by category"""
        if category:
            return self._categories.get(category, [])
        return self._registry.list_tools()
    
    def get_categories(self) -> List[str]:
        """Get all categories"""
        return list(self._categories.keys())
    
    def get_schemas(self) -> List[Dict]:
        """Get schemas for all tools"""
        return self._registry.get_schemas()
    
    def set_memory_service(self, memory_service) -> None:
        """Set memory service for tool result storage"""
        self._memory_service = memory_service
    
    async def execute(
        self,
        tool_name: str,
        arguments: Dict,
        store_in_memory: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a tool with full validation and logging.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments
            store_in_memory: Whether to store result in memory
            
        Returns:
            dict: Execution result
        """
        start_time = datetime.now()
        
        # Get tool
        tool = self.get(tool_name)
        if not tool:
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
            
            # Store in memory if successful
            if store_in_memory and status == "success" and self._memory_service:
                self._memory_service.add(
                    f"Tool: {tool_name}\nArgs: {json.dumps(arguments)}\nResult: {json.dumps(result)}",
                    task_type="tool_execution"
                )
            
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
        error: str = None
    ) -> None:
        """Log tool execution"""
        log_entry = {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "status": status,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        self._execution_log.append(log_entry)
        
        # Keep max log size
        if len(self._execution_log) > self._max_log_size:
            self._execution_log = self._execution_log[-self._max_log_size:]
    
    def get_execution_log(self, limit: int = 10) -> List[Dict]:
        """Get recent execution log"""
        return self._execution_log[-limit:]
    
    def get_tool_stats(self) -> Dict[str, Any]:
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
        """
        Intelligent tool selection based on task description.
        
        Uses simple keyword matching for now.
        Can be enhanced with LLM-based selection.
        """
        task_lower = task_description.lower()
        
        # Keywords to tool mapping
        keyword_tools = {
            "calculate": ["calculator"],
            "math": ["calculator"],
            "remember": ["search_memory"],
            "search": ["search_memory"],
            "time": ["get_time"],
            "clock": ["get_time"],
        }
        
        for keywords, tool_names in keyword_tools.items():
            if keywords in task_lower:
                # Return first available tool
                for tool_name in tool_names:
                    if self.get(tool_name):
                        return tool_name
        
        return None


# Default tool manager
_default_tool_manager: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    """Get singleton ToolManager"""
    global _default_tool_manager
    if _default_tool_manager is None:
        _default_tool_manager = ToolManager()
        
        # Register built-in tools
        _default_tool_manager.register(Tool(
            name="calculator",
            description="Evaluate a mathematical expression",
            parameters=[
                ToolParameter("expression", "string", "The expression to evaluate", required=True)
            ],
            handler=tool_calculator,
            category="utility",
            timeout_seconds=10
        ))
        
        _default_tool_manager.register(Tool(
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
        
        _default_tool_manager.register(Tool(
            name="get_time",
            description="Get current date and time",
            parameters=[],
            handler=tool_get_time,
            category="utility",
            timeout_seconds=5
        ))
    
    return _default_tool_manager