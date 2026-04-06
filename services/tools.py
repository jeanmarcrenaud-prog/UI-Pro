# services/tools.py - Tools / Function Calling
#
# Tool system similar to OpenAI function calling:
# - Tool definitions with schemas
# - Tool execution with validation
# - Tool result handling

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
    
    async def execute(self, arguments: Dict) -> Dict[str, Any]:
        """Execute tool with arguments"""
        try:
            # Validate required parameters
            for param in self.parameters:
                if param.required and param.name not in arguments:
                    return {
                        "status": "error",
                        "error": f"Missing required parameter: {param.name}"
                    }
            
            # Execute handler
            if self.handler:
                result = await self.handler(arguments)
            elif self.sync_handler:
                # Run sync handler in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: self.sync_handler(arguments))
            else:
                return {
                    "status": "error",
                    "error": "No handler defined"
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
    "create_tool"
]