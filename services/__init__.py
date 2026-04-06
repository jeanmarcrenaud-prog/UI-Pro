# services/ - Business Logic Layer
#
# Cette couche abstrait la logique métier:
# - model_service: Gestion modèles LLM avec fallback
# - memory_service: Encapsulation FAISS
# - chat_service: Orchestration des conversations
# - api: Facade unifiée pour tous les services

from .base import BaseService, ServiceMetrics
from .model_service import ModelService, get_model_service
from .memory_service import MemoryService, get_memory_service
from .chat_service import ChatService, get_chat_service
from .api import ServiceAPI, get_service_api, get_chat, get_model, get_memory

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
]