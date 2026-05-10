# services/ - Business Logic Layer
#
# Cette couche abstrait la logique métier:
# - model_service: Gestion modèles LLM avec fallback
# - memory_service: Encapsulation FAISS
# NOTE: chat_service.py supprimé - utiliser streaming.py + WebSocket pour le chat
# - api: Facade unifiée pour tous les services
# - streaming: Real-time streaming responses
# - error_handler: Comprehensive error handling
# - tools: Function calling / tools
# - llm_router: Advanced LLM routing
# NOTE: agents.py supprimé - utiliser agents/agent.py pour les agents

from .base import BaseService, ServiceMetrics
from .model_service import ModelService, get_model_service
from .memory_service import MemoryService, get_memory_service
from .service_api import ServiceAPI, get_service_api, get_streaming, get_model, get_memory
from .llm_router import LLMRouter, TaskType, RouterConfig, get_llm_router
from .streaming import StreamingService, StreamChunk, StreamConfig, StreamStatus, get_streaming_service
from .error_handler import ErrorHandler, ErrorDetails, ErrorCategory, get_error_handler
from .tools import Tool, ToolParameter, ToolCall, ToolManager, get_tool_manager, create_tool

__all__ = [
    # Base
    "BaseService",
    "ServiceMetrics",
    # Core Services
    "ModelService",
    "get_model_service",
    "MemoryService", 
    "get_memory_service",
    # API Facade
    "ServiceAPI",
    "get_service_api",
    "get_streaming",
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
    "ToolManager",
    "get_tool_manager",
    "create_tool",
]