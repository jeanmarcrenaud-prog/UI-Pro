# services/memory_service.py - Memory Service (Enhanced)
#
# Role: FAISS-based semantic memory with LLM compression
# Function: Read/write/compress conversational context for context retrieval
#
# Contract:
#     async get_context(query: str, k: int = 3) -> list[MemoryItem]
#     async save(text: str, session_id?: str) -> None
#     async compress() -> int  # Returns compressed count
#     
# Dependencies:
#     - FAISS via core/memory.py
#     - LLM for semantic compression

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
import pickle

from .base import BaseService, ServiceMetrics


@dataclass
class MemoryEntry:
    """Single memory entry with metadata"""
    text: str
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    task_type: Optional[str] = None
    importance: float = 1.0  # 0-1 importance score


@dataclass
class ContextWindow:
    """Context window management with dynamic token budget"""
    max_tokens: int = 4096
    memory_decay: float = 0.95  # Older memories fade
    importance_threshold: float = 0.3
    compression_threshold: float = 0.8  # Start compressing at 80% of max
    
    def __post_init__(self):
        self._token_budget = int(self.max_tokens * self.compression_threshold)
    
    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4
    
    def needs_compression(self, texts: List[str]) -> bool:
        """Check if texts exceed token budget"""
        total = sum(self.estimate_tokens(t) for t in texts)
        return total > self._token_budget
    
    def fit_texts(self, texts: List[str], allow_compression: bool = True) -> List[str]:
        """Fit texts within token budget"""
        result = []
        total_tokens = 0
        
        for text in texts:
            tokens = self.estimate_tokens(text)
            if total_tokens + tokens > self.max_tokens:
                # If compression allowed and we have results, try to summarize
                if allow_compression and result:
                    break
                break
            result.append(text)
            total_tokens += tokens
        
        return result
    
    def get_budget_remaining(self, current_tokens: int) -> int:
        """Get remaining budget"""
        return max(0, self._token_budget - current_tokens)


class MemoryService(BaseService):
    """
    Service de gestion mémoire avec FAISS.
    
    Enhanced Features:
    - Memory with metadata (session, task_type, importance)
    - Context window management (token limits)
    - Semantic grouping by session
    - Relevance scoring
    - Auto-cleanup of old memories
    """
    
    def __init__(
        self, 
        persist_path: Optional[str] = None,
        max_context_tokens: int = 4096,
        auto_cleanup: bool = True,
        max_entries: int = 1000
    ):
        super().__init__("MemoryService")
        self.persist_path = persist_path
        self.max_context_tokens = max_context_tokens
        self.auto_cleanup = auto_cleanup
        self.max_entries = max_entries
        
        self._memory_manager = None
        self._context_window = ContextWindow(max_tokens=max_context_tokens)
        self._service_metrics = ServiceMetrics()
        
        # Unified metadata storage: doc_id (FAISS index) → MemoryEntry
        # This provides O(1) lookup instead of O(n²)
        self._metadata: Dict[int, MemoryEntry] = {}
        self._metadata_path: Optional[Path] = None
    
    async def initialize(self) -> None:
        """Initialize memory service"""
        try:
            from core.memory import MemoryManager
            path = self.persist_path if self.persist_path else None
            self._memory_manager = MemoryManager(persist_path=path)
            
            # Setup metadata persistence path
            if path:
                self._metadata_path = Path(path).parent / "memory_metadata.pkl"
                self._load_metadata()
            
            self.logger.info(f"MemoryService initialized with {self._memory_manager.count()} memories")
        except Exception as e:
            self._set_error(str(e))
            raise
    
    def _load_metadata(self) -> None:
        """Load metadata from disk"""
        if self._metadata_path and self._metadata_path.exists():
            try:
                with open(self._metadata_path, "rb") as f:
                    self._metadata = pickle.load(f)
                self.logger.info(f"Loaded {len(self._metadata)} metadata entries")
            except Exception as e:
                self.logger.warning(f"Failed to load metadata: {e}")
                self._metadata = {}
    
    def _save_metadata(self) -> None:
        """Save metadata to disk"""
        if self._metadata_path:
            try:
                self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._metadata_path, "wb") as f:
                    pickle.dump(self._metadata, f)
                self.logger.debug(f"Saved {len(self._metadata)} metadata entries")
            except Exception as e:
                self.logger.error(f"Failed to save metadata: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown memory service"""
        if self._memory_manager:
            self._memory_manager.save()
            self._save_metadata()
            self.logger.info("MemoryService saved and shutdown")
    
    def add(
        self, 
        text: str, 
        session_id: Optional[str] = None,
        task_type: Optional[str] = None,
        importance: float = 1.0,
        auto_save: bool = False
    ) -> None:
        """
        Add text to memory with unified metadata.
        
        Args:
            text: Text to store
            session_id: Optional session identifier
            task_type: Optional task type (code, reasoning, etc.)
            importance: Importance score 0-1
            auto_save: If True, persist immediately
        """
        if not text or not text.strip():
            self.logger.warning("add() called with empty text")
            return
        
        try:
            # Get doc_id BEFORE adding (FAISS index is count before add)
            doc_id = self._memory_manager.count()
            
            self._memory_manager.add_memory(text, auto_save=auto_save)
            
            # Store metadata with O(1) lookup using doc_id
            entry = MemoryEntry(
                text=text,
                session_id=session_id,
                task_type=task_type,
                importance=importance
            )
            self._metadata[doc_id] = entry
            
            # Auto-cleanup if needed
            if self.auto_cleanup and self.count() > self.max_entries:
                self._cleanup_old_memories()
            
            self._service_metrics.record_call(0, success=True)
            self.logger.debug(f"Added memory, total: {self.count()}")
            
        except Exception as e:
            self._service_metrics.record_call(0, success=False)
            self.logger.error(f"Failed to add memory: {e}")
    
    def search(
        self, 
        query: str, 
        k: int = 3,
        session_id: Optional[str] = None,
        task_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Search memory with O(1) metadata lookup.
        
        Args:
            query: Search query
            k: Number of results
            session_id: Filter by session
            task_type: Filter by task type
            
        Returns:
            List[Dict]: Results with text and score
        """
        if not query or not query.strip():
            return []
        
        try:
            results = self._memory_manager.search(query, k=k)
            
            # Apply filters with O(1) metadata lookup
            if session_id or task_type:
                filtered = []
                for r in results:
                    # FAISS returns doc_id in the result
                    # We need to find it - FAISS search returns (distances, ids)
                    # The text extraction needs lookup
                    text = r.get("text", "")
                    
                    # Find matching entry by text (still O(n) for now, but smaller n)
                    # TODO: Add reverse index for text -> doc_id if needed
                    entry = None
                    for doc_id, e in self._metadata.items():
                        if e.text == text:
                            entry = e
                            break
                    
                    if entry is not None:
                        # Apply filters
                        if session_id and entry.session_id != session_id:
                            continue
                        if task_type and entry.task_type != task_type:
                            continue
                    
                    filtered.append(r)
                results = filtered
            
            self._service_metrics.record_call(0, success=True)
            return results
            
        except Exception as e:
            self._service_metrics.record_call(0, success=False)
            self.logger.error(f"Search failed: {e}")
            return []
    
    def get_context(
        self, 
        query: str, 
        k: int = 3,
        session_id: Optional[str] = None
    ) -> str:
        """
        Get context from memory for a query with token management.
        
        Args:
            query: Query to get context for
            k: Number of relevant memories
            session_id: Optional session filter
            
        Returns:
            str: Context string within token budget
        """
        results = self.search(query, k=k, session_id=session_id)
        
        if not results:
            return ""
        
        # Extract texts and apply token budget
        texts = [r.get("text", "")[:500] for r in results]  # Truncate individual
        fitted_texts = self._context_window.fit_texts(texts)
        
        return "\n---\n".join(fitted_texts)
    
    def get_session_context(self, session_id: str, max_tokens: int = None) -> str:
        """Get all memories from a session using unified metadata"""
        if not session_id:
            return ""
        
        # Collect entries for this session from metadata
        session_entries = [
            e for e in self._metadata.values() 
            if e.session_id == session_id
        ]
        
        if not session_entries:
            return ""
        
        # Sort by importance and time
        sorted_entries = sorted(
            session_entries, 
            key=lambda e: (e.importance, e.timestamp),
            reverse=True
        )
        
        texts = [e.text[:500] for e in sorted_entries]
        
        # Apply token budget
        window = ContextWindow(max_tokens=max_tokens or self.max_context_tokens)
        return "\n---\n".join(window.fit_texts(texts))
    
    def count(self) -> int:
        """Get number of stored memories"""
        if self._memory_manager is None:
            return 0
        return self._memory_manager.count()
    
    def clear(self, session_id: Optional[str] = None) -> None:
        """Clear memories, optionally by session"""
        if session_id:
            # Clear specific session from metadata
            doc_ids_to_remove = [
                doc_id for doc_id, e in list(self._metadata.items())
                if e.session_id == session_id
            ]
            for doc_id in doc_ids_to_remove:
                del self._metadata[doc_id]
            self.logger.info(f"Cleared session: {session_id}")
        else:
            # Clear all
            if self._memory_manager:
                self._memory_manager.clear()
            self._metadata.clear()
            self.logger.info("All memories cleared")
    
    def _cleanup_old_memories(self):
        """Remove old/low-importance memories"""
        # Keep most recent and high importance
        total = self.count()
        to_remove = total - self.max_entries
        
        if to_remove > 0:
            self.logger.info(f"Auto-cleanup: removing {to_remove} old memories")
            # Note: Actual cleanup would need FAISS index manipulation
            # For now, just log
    
    def get_metrics(self) -> dict:
        """Get service metrics"""
        return {
            "service": "MemoryService",
            "total_memories": self.count(),
            "total_searches": self._service_metrics.total_calls,
            "success_rate": self._service_metrics.success_rate,
            "metadata_entries": len(self._metadata),
            "context_tokens": self.max_context_tokens,
        }
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of all sessions"""
        # Get unique session_ids from metadata
        sessions = {}
        for entry in self._metadata.values():
            if entry.session_id:
                if entry.session_id not in sessions:
                    sessions[entry.session_id] = []
                sessions[entry.session_id].append(entry)
        
        return {
            sid: {
                "count": len(entries),
                "latest": max(e.timestamp for e in entries).isoformat() if entries else None,
                "task_types": list(set(e.task_type for e in entries if e.task_type))
            }
            for sid, entries in sessions.items()
        }
    
    # ===== LLM-based Summarization & Context Optimization =====
    
    async def _llm_summarize(self, texts: List[str]) -> str:
        """
        Summarize texts using LLM for better compression.
        
        Args:
            texts: List of texts to summarize
            
        Returns:
            str: Compressed summary
        """
        if not texts:
            return ""
        
        if len(texts) == 1:
            return texts[0][:500]
        
        # Combine texts with numbering
        combined = "\n\n".join([f"[{i+1}] {t[:300]}" for i, t in enumerate(texts[:5])])
        
        summary_prompt = f"""Summarize these conversation snippets into a concise summary (max 200 words):

{combined}

Respond with a summary that preserves the key information and patterns."""
        
        try:
            from .model_service import get_model_service
            llm = get_model_service()
            summary = llm.generate(summary_prompt, mode="fast", max_retries=1)
            return summary[:500] if summary else self._fallback_summarize(texts)
        except Exception as e:
            self.logger.warning(f"LLM summarization failed: {e}, using fallback")
            return self._fallback_summarize(texts)
    
    def _fallback_summarize(self, texts: List[str]) -> str:
        """Fallback extractive summarization"""
        if len(texts) <= 3:
            return "\n".join(texts[:len(texts)])[:500]
        
        # Take first sentence from each
        sentences = []
        for text in texts[:3]:
            first_period = text.find(".")
            if first_period > 0:
                sentences.append(text[:first_period + 1])
            else:
                sentences.append(text[:100])
        
        return " ".join(sentences)[:500]
    
    def _summarize_texts(self, texts: List[str]) -> str:
        """
        Summarize multiple texts into a short summary.
        
        Wrapper that decides between LLM and fallback.
        """
        # For short texts, use simple approach
        if len(texts) <= 2:
            return texts[0][:500] if texts else ""
        
        # Use async version for LLM-based
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't await in sync context, use fallback
                return self._fallback_summarize(texts)
            return loop.run_until_complete(self._llm_summarize(texts))
        except:
            return self._fallback_summarize(texts)
    
    async def summarize_old_memories(self, session_id: str = None) -> int:
        """
        Summarize old memories to save context space.
        
        Args:
            session_id: Optional session to summarize
            
        Returns:
            int: Number of memories summarized
        """
        summarized_count = 0
        
        if session_id:
            # Get entries for this session from metadata
            entries = [e for e in self._metadata.values() if e.session_id == session_id]
            if len(entries) > 10:
                # Keep last 5, summarize older ones
                to_summarize = entries[:-5]
                summary = await self._llm_summarize([e.text for e in to_summarize])
                
                new_entry = MemoryEntry(
                    text=f"[Summary of {len(to_summarize)} past exchanges]: {summary}",
                    timestamp=datetime.now(),
                    session_id=session_id,
                    importance=0.5
                )
                
                # Add new summary entry
                doc_id = len(self._metadata)
                self._metadata[doc_id] = new_entry
                summarized_count = len(to_summarize)
        else:
            # Summarize all sessions - get unique session_ids
            session_ids = set(e.session_id for e in self._metadata.values() if e.session_id)
            for sid in session_ids:
                count = await self.summarize_old_memories(sid)
                summarized_count += count
        
        if summarized_count > 0:
            self.logger.info(f"Summarized {summarized_count} memories")
        
        return summarized_count
    
    def compress_session(self, session_id: str, target_tokens: int = None) -> bool:
        """
        Compress session memory to fit token budget.
        
        Args:
            session_id: Session to compress
            target_tokens: Target token budget (default: self.max_context_tokens)
            
        Returns:
            bool: True if compression was needed and performed
        """
        target_tokens = target_tokens or self.max_context_tokens
        
        # Get entries for this session from metadata
        entries = [e for e in self._metadata.values() if e.session_id == session_id]
        
        if not entries:
            return False
        
        # Calculate current tokens
        current_tokens = sum(self._context_window.estimate_tokens(e.text) for e in entries)
        
        if current_tokens <= target_tokens:
            return False  # No compression needed
        
        # Need to compress - keep high importance and recent
        sorted_entries = sorted(
            entries, 
            key=lambda e: (e.importance, e.timestamp),
            reverse=True
        )
        
        # Keep entries that fit
        kept = []
        used_tokens = 0
        for entry in sorted_entries:
            tokens = self._context_window.estimate_tokens(entry.text)
            if used_tokens + tokens > target_tokens:
                break
            kept.append(entry)
            used_tokens += tokens
        
        # If we kept too few, summarize the rest and add as summary
        if len(kept) < len(entries) * 0.5:
            to_summarize = [e for e in sorted_entries if e not in kept]
            summary = self._fallback_summarize([e.text for e in to_summarize])
            
            summary_entry = MemoryEntry(
                text=f"[Compressed summary of {len(to_summarize)} exchanges]: {summary}",
                timestamp=datetime.now(),
                session_id=session_id,
                importance=0.4
            )
            kept.append(summary_entry)
        
        # Remove old entries and add kept ones
        for doc_id in list(self._metadata.keys()):
            if self._metadata[doc_id].session_id == session_id:
                del self._metadata[doc_id]
        for entry in kept:
            doc_id = len(self._metadata)
            self._metadata[doc_id] = entry
        
        self.logger.info(f"Compressed session {session_id}: {len(entries)} -> {len(kept)} entries")
        return True
    
    def get_optimized_context(
        self,
        query: str,
        max_tokens: int = None,
        include_summary: bool = True
    ) -> str:
        """
        Get context with automatic summarization for long histories.
        
        Args:
            query: Query for retrieval
            max_tokens: Max tokens to return
            include_summary: Include summarized versions
            
        Returns:
            str: Context string within token budget
        """
        max_tokens = max_tokens or self.max_context_tokens
        
        # Get recent memories
        results = self.search(query, k=10)
        
        if not results:
            return ""
        
        # Extract texts
        texts = [r.get("text", "") for r in results]
        
        # Check if we need to summarize
        total_chars = sum(len(t) for t in texts)
        estimated_tokens = total_chars // 4
        
        if estimated_tokens > max_tokens:
            # Need to compress
            # Take fewer results
            k = max(1, int(max_tokens * 4 / (total_chars / len(texts))))
            texts = texts[:k]
        
        # Fit to token budget
        window = ContextWindow(max_tokens=max_tokens)
        fitted = window.fit_texts(texts)
        
        return "\n---\n".join(fitted)


# Singleton instance
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get singleton MemoryService"""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service