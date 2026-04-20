# services/ - Business Logic Layer
#
# Cette couche abstrait la logique métier:
# - model_service: Gestion modèles LLM avec fallback
# - memory_service: Encapsulation FAISS
# - chat_service: Orchestration des conversations
# - api: Facade unifiée pour tous les services
# - streaming: Real-time streaming responses
# - error_handler: Comprehensive error handling
# - tools: Function calling / tools
# - agents: Multi-step reasoning agents
# - llm_router: Advanced LLM routing

from .base import BaseService, ServiceMetrics
from .model_service import ModelService, get_model_service
from .memory_service import MemoryService, get_memory_service
from .chat_service import ChatService, get_chat_service
from .service_api import ServiceAPI, get_service_api, get_chat, get_model, get_memory
from .llm_router import LLMRouter, TaskType, RouterConfig, get_llm_router
from .streaming import StreamingService, StreamChunk, StreamConfig, StreamStatus, get_streaming_service
from .error_handler import ErrorHandler, ErrorDetails, ErrorCategory, get_error_handler
from .tools import Tool, ToolParameter, ToolCall, ToolRegistry, get_tool_registry, create_tool
from .agents import Agent, AgentConfig, AgentStep, AgentStatus, get_agent

__all__ = [
    # Base
    "BaseService",
    "ServiceMetrics",
    # Core Services
    "ModelService",
    "get_model_service",
    "MemoryService", 
    "get_memory_service",
    "ChatService",
    "get_chat_service",
    # API Facade
    "ServiceAPI",
    "get_service_api",
    "get_chat",
    "get_model",
    "get_memory",
    # LLM Router
    "LLMRouter",
    "TaskType",
    "RouterConfig",
    "get_llm_router",
    # Streaming
    "StreamingService",
    "StreamChunk",
    "StreamConfig",
    "StreamStatus",
    "get_streaming_service",
    # Error Handling
    "ErrorHandler",
    "ErrorDetails",
    "ErrorCategory",
    "get_error_handler",
    # Tools
    "Tool",
    "ToolParameter",
    "ToolCall",
    "ToolRegistry",
    "get_tool_registry",
    "create_tool",
    # Agents
    "Agent",
    "AgentConfig",
    "AgentStep",
    "AgentStatus",
    "get_agent",
]