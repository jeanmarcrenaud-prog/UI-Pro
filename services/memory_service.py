# services/memory_service.py - Memory Service (Refactored)
#
# Role: Unified memory service with persistent metadata
# - FAISS vector search
# - Rich metadata with UUID-based entries
# - Context building with token budget
# - Session management

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
import pickle
import uuid

from .base import BaseService, ServiceMetrics


@dataclass
class MemoryEntry:
    """Unified memory entry with stable UUID"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    task_type: Optional[str] = None
    importance: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "task_type": self.task_type,
            "importance": self.importance,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MemoryEntry":
        data = data.copy()
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ContextBuilder:
    """Smart context management with token budget"""
    
    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens
        self.compression_threshold = 0.8

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation"""
        return len(text) // 4

    def fit(self, texts: List[str], max_tokens: Optional[int] = None) -> List[str]:
        """Fit texts within token budget"""
        max_t = max_tokens or self.max_tokens
        result = []
        total = 0

        for text in texts:
            tokens = self.estimate_tokens(text)
            if total + tokens > max_t:
                break
            result.append(text)
            total += tokens
        
        return result


class MemoryService(BaseService):
    """
    Unified memory service with persistent metadata.
    """
    
    def __init__(
        self, 
        persist_path: Optional[str] = None,
        max_tokens: int = 4096,
        auto_compress: bool = True
    ):
        super().__init__("MemoryService")
        self.persist_path = persist_path
        self.max_tokens = max_tokens
        self.auto_compress = auto_compress
        
        # Core storage
        self._vector_store = None
        
        # Unified entry storage: id -> MemoryEntry
        self._entries: Dict[str, MemoryEntry] = {}
        
        # Session index: session_id -> list[entry_id]
        self._session_index: Dict[str, List[str]] = defaultdict(list)
        
        # Context builder
        self.context_builder = ContextBuilder(max_tokens=max_tokens)
        
        # Metrics
        self._service_metrics = ServiceMetrics()
        
        # Persistence
        self._entries_path: Optional[Path] = None

    # ====================== INITIALIZATION ======================
    
    async def initialize(self) -> None:
        """Async initialization"""
        try:
            from core.memory import get_memory_manager
            self._vector_store = get_memory_manager()
            
            # Setup persistence
            if self.persist_path:
                self._entries_path = Path(self.persist_path).parent / "memory_entries.pkl"
                self._load_entries()
            
            self.logger.info(f"MemoryService initialized - {len(self._entries)} entries")
        except Exception as e:
            self._set_error(str(e))
            raise

    def _load_entries(self) -> None:
        """Load entries from disk"""
        if self._entries_path and self._entries_path.exists():
            try:
                with open(self._entries_path, "rb") as f:
                    data = pickle.load(f)
                    self._entries = {k: MemoryEntry.from_dict(v) for k, v in data.items()}
                    # Rebuild session index
                    for entry in self._entries.values():
                        if entry.session_id:
                            self._session_index[entry.session_id].append(entry.id)
                self.logger.info(f"Loaded {len(self._entries)} entries")
            except Exception as e:
                self.logger.warning(f"Failed to load entries: {e}")
                self._entries = {}

    def _save_entries(self) -> None:
        """Save entries to disk"""
        if self._entries_path:
            try:
                self._entries_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._entries_path, "wb") as f:
                    data = {k: v.to_dict() for k, v in self._entries.items()}
                    pickle.dump(data, f)
                self.logger.debug(f"Saved {len(self._entries)} entries")
            except Exception as e:
                self.logger.error(f"Failed to save entries: {e}")

    async def shutdown(self) -> None:
        """Clean shutdown"""
        if self._vector_store:
            self._vector_store.save()
        self._save_entries()
        self.logger.info("MemoryService shutdown completed")

    # ====================== CORE OPERATIONS ======================

    async def add(
        self,
        text: str,
        session_id: Optional[str] = None,
        task_type: Optional[str] = None,
        importance: float = 1.0,
        metadata: Optional[Dict] = None,
        auto_save: bool = False
    ) -> Optional[str]:
        """Add memory with metadata"""
        if not text or not text.strip():
            return None

        entry = MemoryEntry(
            text=text.strip(),
            session_id=session_id,
            task_type=task_type,
            importance=importance,
            metadata=metadata or {}
        )

        try:
            # Add to vector store
            self._vector_store.add_memory(entry.text, auto_save=auto_save)
            
            # Store entry
            self._entries[entry.id] = entry
            
            # Update session index
            if session_id:
                self._session_index[session_id].append(entry.id)
            
            self._service_metrics.record_call(0, success=True)
            self.logger.debug(f"Memory added [{entry.id[:8]}] session={session_id}")
            
            return entry.id

        except Exception as e:
            self._service_metrics.record_call(0, success=False)
            self.logger.error(f"Failed to add memory: {e}")
            return None

    async def search(
        self,
        query: str,
        k: int = 5,
        session_id: Optional[str] = None,
        task_type: Optional[str] = None
    ) -> List[Dict]:
        """Semantic search with filters"""
        if not query or not query.strip():
            return []

        try:
            # Get more results for filtering
            vector_results = self._vector_store.search(query, k=k * 2)
            
            # Match with entries (text -> entry lookup would be O(n))
            # For now, iterate through vector results and find matching entries
            results = []
            result_texts = {r.get("text", ""): r for r in vector_results}
            
            for entry in self._entries.values():
                text = entry.text
                if text not in result_texts:
                    continue
                
                # Apply filters
                if session_id and entry.session_id != session_id:
                    continue
                if task_type and entry.task_type != task_type:
                    continue
                
                results.append({
                    "id": entry.id,
                    "text": entry.text,
                    "score": result_texts[text].get("score", 0.0),
                    "session_id": entry.session_id,
                    "task_type": entry.task_type,
                    "importance": entry.importance
                })
                
                if len(results) >= k:
                    break

            self._service_metrics.record_call(0, success=True)
            return results

        except Exception as e:
            self._service_metrics.record_call(0, success=False)
            self.logger.error(f"Search failed: {e}")
            return []

    # ====================== CONTEXT ======================

    async def get_context(
        self,
        query: str,
        k: int = 5,
        session_id: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Get optimized context for query"""
        results = await self.search(query, k=k, session_id=session_id)
        
        if not results:
            return ""

        texts = [r.get("text", "")[:500] for r in results]
        fitted = self.context_builder.fit(texts, max_tokens)

        return "\n---\n".join(fitted)

    async def get_session_context(
        self,
        session_id: str,
        max_tokens: Optional[int] = None
    ) -> str:
        """Get full session context"""
        if not session_id:
            return ""

        entry_ids = self._session_index.get(session_id, [])
        entries = [self._entries[eid] for eid in entry_ids if eid in self._entries]
        
        if not entries:
            return ""

        # Sort by importance then timestamp
        sorted_entries = sorted(
            entries,
            key=lambda e: (e.importance, e.timestamp),
            reverse=True
        )

        texts = [e.text[:500] for e in sorted_entries]
        return "\n---\n".join(self.context_builder.fit(texts, max_tokens))

    # ====================== COMPRESSION ======================

    async def compress_session(self, session_id: str) -> bool:
        """Compress session memory"""
        self.logger.info(f"Session compression requested for {session_id}")
        # TODO: Implement with LLM
        return True

    async def summarize_old_memories(self, session_id: Optional[str] = None) -> int:
        """Summarize old memories"""
        self.logger.info(f"Summarization requested for session={session_id}")
        # TODO: Implement with LLM
        return 0

    # ====================== UTILITIES ======================

    def count(self) -> int:
        return len(self._entries)

    def clear(self, session_id: Optional[str] = None) -> None:
        """Clear memories"""
        if session_id:
            entry_ids = self._session_index.pop(session_id, [])
            for eid in entry_ids:
                self._entries.pop(eid, None)
            self.logger.info(f"Cleared session: {session_id}")
        else:
            self._entries.clear()
            self._session_index.clear()
            if self._vector_store:
                self._vector_store.clear()
            self.logger.info("All memories cleared")

    def get_stats(self) -> Dict:
        """Get service statistics"""
        return {
            "total_entries": self.count(),
            "active_sessions": len(self._session_index),
            "max_tokens": self.max_tokens,
            "vector_store": self._vector_store.count() if self._vector_store else 0
        }

    def get_metrics(self) -> Dict:
        """Get service metrics"""
        return {
            "service": "MemoryService",
            "total_entries": self.count(),
            "total_searches": self._service_metrics.total_calls,
            "success_rate": self._service_metrics.success_rate,
            "sessions": len(self._session_index),
            "max_tokens": self.max_tokens,
        }

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of all sessions"""
        return {
            sid: {
                "count": len(eids),
                "entries": [self._entries[eid].to_dict() for eid in eids if eid in self._entries]
            }
            for sid, eids in self._session_index.items()
        }


# ====================== SINGLETON ======================

_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get singleton memory service"""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
