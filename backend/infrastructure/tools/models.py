# backend/infrastructure/tools/models.py
# Role: Data classes for tool definitions and tool call requests

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


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
    parameters: list[ToolParameter]
    handler: Callable | None = None
    timeout_seconds: int = 30
    category: str = "general"

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function calling schema"""
        properties = {}
        required_params = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
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
                    "required": required_params,
                },
            },
        }

    def validate_arguments(self, arguments: dict) -> tuple[bool, str | None]:
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

    async def execute(self, arguments: dict) -> dict[str, Any]:
        """Execute tool with arguments and validation"""
        try:
            is_valid, error_msg = self.validate_arguments(arguments)
            if not is_valid:
                return {"status": "error", "error": error_msg}

            if not self.handler:
                return {"status": "error", "error": "No handler defined"}

            try:
                result = await asyncio.wait_for(
                    self.handler(arguments), timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                return {
                    "status": "error",
                    "error": f"Tool timed out after {self.timeout_seconds}s",
                }

            return {"status": "success", "result": result}

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"status": "error", "error": str(e)}


@dataclass
class ToolCall:
    """Represents a tool call request"""

    id: str
    name: str
    arguments: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
