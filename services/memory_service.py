# services/memory_service.py - Memory Service
#
# Encapsulation de la mémoire FAISS avec:
# - Interface unifiée
# - Auto-save
# - Recherche contextuelle

import logging
from typing import Optional
from datetime import datetime

from .base import BaseService, ServiceMetrics


class MemoryService(BaseService):
    """
    Service de gestion mémoire avec FAISS.
    
    Encapsule:
    - MemoryManager de models/memory.py
    - Auto-save après chaque ajout
    - Interface unifiée
    """
    
    def __init__(self, persist_path: Optional[str] = None):
        super().__init__("MemoryService")
        self.persist_path = persist_path
        self._memory_manager = None
        self.service_metrics = ServiceMetrics()
    
    async def initialize(self) -> None:
        """Initialize memory service"""
        try:
            from models.memory import MemoryManager
            path = self.persist_path if self.persist_path else None
            self._memory_manager = MemoryManager(persist_path=path)
            self.logger.info(f"MemoryService initialized with {self._memory_manager.count()} memories")
        except Exception as e:
            self._set_error(str(e))
            raise
    
    async def shutdown(self) -> None:
        """Shutdown memory service"""
        if self._memory_manager:
            self._memory_manager.save()
            self.logger.info("MemoryService saved and shutdown")
    
    def add(self, text: str) -> None:
        """
        Add text to memory.
        
        Args:
            text: Text to store
        """
        if not text or not text.strip():
            self.logger.warning("add() called with empty text")
            return
        
        try:
            self._memory_manager.add_memory(text)
            self.service_metrics.record_call(0, success=True)
            self.logger.debug(f"Added memory, total: {self.count()}")
        except Exception as e:
            self.service_metrics.record_call(0, success=False)
            self.logger.error(f"Failed to add memory: {e}")
    
    def search(self, query: str, k: int = 3) -> list:
        """
        Search memory.
        
        Args:
            query: Search query
            k: Number of results
            
        Returns:
            list: List of results with text and score
        """
        if not query or not query.strip():
            return []
        
        try:
            results = self._memory_manager.search(query, k=k)
            self.service_metrics.record_call(0, success=True)
            return results
        except Exception as e:
            self.service_metrics.record_call(0, success=False)
            self.logger.error(f"Search failed: {e}")
            return []
    
    def count(self) -> int:
        """Get number of stored memories"""
        if self._memory_manager is None:
            return 0
        return self._memory_manager.count()
    
    def clear(self) -> None:
        """Clear all memories"""
        if self._memory_manager:
            self._memory_manager.clear()
            self.logger.info("Memory cleared")
    
    def get_context(self, query: str, k: int = 3) -> str:
        """
        Get context from memory for a query.
        
        Args:
            query: Query to get context for
            k: Number of relevant memories
            
        Returns:
            str: Context string from relevant memories
        """
        results = self.search(query, k=k)
        if not results:
            return ""
        
        context_parts = []
        for r in results:
            text = r.get("text", "")[:200]  # Truncate long texts
            context_parts.append(text)
        
        return "\n---\n".join(context_parts)
    
    def get_metrics(self) -> dict:
        """Get service metrics"""
        return {
            "service": "MemoryService",
            "total_memories": self.count(),
            "total_searches": self.service_metrics.total_calls,
            "success_rate": self.service_metrics.success_rate,
        }


# Singleton instance
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get singleton MemoryService"""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service