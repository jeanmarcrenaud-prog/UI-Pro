# services/api.py - Internal Service API
#
# API interne unifiée pour les services:
# - ChatService (pipeline orchestration)
# - ModelService (LLM management)
# - MemoryService (context retrieval)
#
# Usage:
#   api = ServiceAPI()
#   result = await api.chat.execute_task("Create a FastAPI app")
#   status = await api.chat.get_status()
#   metrics = api.model.get_metrics()

from typing import Optional
from .base import BaseService
from .chat_service import ChatService, get_chat_service
from .model_service import ModelService, get_model_service
from .memory_service import MemoryService, get_memory_service


class ServiceAPI:
    """
    Internal API facade for all services.
    
    Provides:
    - Unified access to all services
    - Health checks for each service
    - Aggregated metrics
    """
    
    def __init__(self):
        self._chat: Optional[ChatService] = None
        self._model: Optional[ModelService] = None
        self._memory: Optional[MemoryService] = None
        self._initialized = False
    
    @property
    def chat(self) -> ChatService:
        """Get chat service (lazy init)"""
        if self._chat is None:
            self._chat = get_chat_service()
        return self._chat
    
    @property
    def model(self) -> ModelService:
        """Get model service (lazy init)"""
        if self._model is None:
            self._model = get_model_service()
        return self._model
    
    @property
    def memory(self) -> MemoryService:
        """Get memory service (lazy init)"""
        if self._memory is None:
            self._memory = get_memory_service()
        return self._memory
    
    async def initialize(self) -> None:
        """Initialize all services"""
        if self._initialized:
            return
        
        # Initialize model service first
        await self.model.initialize()
        
        # Initialize memory
        await self.memory.initialize()
        
        # Initialize chat (depends on model + memory)
        await self.chat.initialize()
        
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Shutdown all services"""
        if self._chat:
            await self._chat.shutdown()
        if self._model:
            await self._model.shutdown()
        if self._memory:
            await self._memory.shutdown()
        self._initialized = False
    
    def health_check(self) -> dict:
        """Get health status of all services"""
        return {
            "api": "healthy" if self._initialized else "not_initialized",
            "model": self.model.health_check() if self._model else "not_loaded",
            "memory": self.memory.health_check() if self._memory else "not_loaded",
            "chat": self.chat.health_check() if self._chat else "not_loaded",
        }
    
    def get_all_metrics(self) -> dict:
        """Get aggregated metrics from all services"""
        return {
            "api": {
                "initialized": self._initialized
            },
            "model": self.model.get_metrics() if self._model else {},
            "memory": self.memory.get_metrics() if self._memory else {},
            "chat": self.chat.get_metrics() if self._chat else {},
        }


# Singleton instance
_api: Optional[ServiceAPI] = None


def get_service_api() -> ServiceAPI:
    """Get singleton ServiceAPI"""
    global _api
    if _api is None:
        _api = ServiceAPI()
    return _api


# Convenience functions for direct access
async def initialize_services() -> None:
    """Initialize all services"""
    api = get_service_api()
    await api.initialize()


async def shutdown_services() -> None:
    """Shutdown all services"""
    api = get_service_api()
    await api.shutdown()


def get_chat():
    """Get ChatService for task execution"""
    return get_service_api().chat


def get_model():
    """Get ModelService for LLM operations"""
    return get_service_api().model


def get_memory():
    """Get MemoryService for context retrieval"""
    return get_service_api().memory