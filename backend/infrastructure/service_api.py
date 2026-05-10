# services/service_api.py - Internal Service API
#
# API interne unifiée pour les services:
# - StreamingService (chat en temps réel)
# - ModelService (LLM management)
# - MemoryService (context retrieval)
#
# NOTE: ChatService supprimé - utiliser streaming.py directement

from typing import Optional
from .base import BaseService
from .streaming import get_streaming_service
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
        self._model: Optional[ModelService] = None
        self._memory: Optional[MemoryService] = None
        self._initialized = False
    
    @property
    def streaming(self):
        """Get streaming service"""
        return get_streaming_service()
    
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
        
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Shutdown all services"""
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
            "streaming": "available",
        }
    
    def get_all_metrics(self) -> dict:
        """Get aggregated metrics from all services"""
        return {
            "api": {
                "initialized": self._initialized
            },
            "model": self.model.get_metrics() if self._model else {},
            "memory": self.memory.get_metrics() if self._memory else {},
            "streaming": {},
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


def get_streaming():
    """Get StreamingService for real-time chat"""
    return get_service_api().streaming


def get_model():
    """Get ModelService for LLM operations"""
    return get_service_api().model


def get_memory():
    """Get MemoryService for context retrieval"""
    return get_service_api().memory