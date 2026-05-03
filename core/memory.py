# core/memory.py - FAISS Memory Store
#
# Role: Persistent vector memory using FAISS with LRU eviction and compression
# Used by: Memory service, orchestrator
# - Semantic search
# - Index persistence
# - Memory efficiency with LRU eviction

from .logger import get_logger
from pathlib import Path
import os
import pickle
import hashlib
import threading
from typing import List, Dict, Any, Optional
from collections import OrderedDict
import time

# Suppress warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

logger = get_logger(__name__)

# Default config - will be loaded from settings
DEFAULT_PERSIST_PATH = Path("data/memory.index")
DEFAULT_DOCS_PATH = Path("data/memory_docs.pkl")
DEFAULT_MAX_MEMORIES = 10000  # Maximum number of memories to keep
DEFAULT_COMPRESSION_THRESHOLD = 1000  # Compress memories older than this count

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

logger.info("Memory module initialized")

# Model for embeddings
model = SentenceTransformer("all-MiniLM-L6-v2")

# Enhanced MemoryManager class with LRU eviction and compression
class MemoryManager:
    """Memory manager with FAISS index, LRU eviction, compression, and persistence"""
    
    def __init__(self, persist_path: Optional[str] = None, max_memories: Optional[int] = None):
        # Thread safety lock
        self._lock = threading.RLock()
        
        # Default dimension
        self.d = 384
        # Use IndexIDMap for ID-based management (enables add_with_ids)
        base_index = faiss.IndexFlatL2(self.d)
        self.index = faiss.IndexIDMap(base_index)
        self.documents = []  # List of documents in order of addition
        self.access_order = OrderedDict()  # LRU tracking: doc_index -> last_access_time
        self.timestamps = []  # Timestamp for each document
        self.compression_enabled = True
        
        # Configuration
        self.max_memories = max_memories or int(os.getenv("MEMORY_MAX_MEMORIES", str(DEFAULT_MAX_MEMORIES)))
        self.compression_threshold = int(os.getenv("MEMORY_COMPRESSION_THRESHOLD", str(DEFAULT_COMPRESSION_THRESHOLD)))
        
        # Persistence paths
        self.persist_path = Path(persist_path or os.getenv("MEMORY_PERSIST_PATH", str(DEFAULT_PERSIST_PATH)))
        self.docs_path = Path(os.getenv("MEMORY_DOCS_PATH", str(DEFAULT_DOCS_PATH)))
        
        # Load existing data if available
        self._ensure_data_dir()
        self._load()
    
    def _ensure_data_dir(self):
        """Create data directory if needed"""
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _load(self):
        """Load FAISS index and documents from disk"""
        if self.persist_path.exists():
            try:
                loaded = faiss.read_index(str(self.persist_path))
                # Handle both plain index and IndexIDMap
                if isinstance(loaded, faiss.IndexIDMap):
                    self.index = loaded
                else:
                    # Wrap plain index in IndexIDMap
                    self.index = faiss.IndexIDMap(loaded)
                # Sync dimension after loading
                if self.index.ntotal > 0:
                    self.d = self.index.d
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors, dim={self.d}")
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}")
                base_index = faiss.IndexFlatL2(self.d)
                self.index = faiss.IndexIDMap(base_index)
        
        if self.docs_path.exists():
            try:
                with open(self.docs_path, "rb") as f:
                    data = pickle.load(f)
                    # Handle both old format (just documents) and new format (with metadata)
                    if isinstance(data, list):
                        self.documents = data
                        self.timestamps = [time.time()] * len(data)  # Assume current time for old data
                    elif isinstance(data, dict) and 'documents' in data:
                        self.documents = data['documents']
                        self.timestamps = data.get('timestamps', [time.time()] * len(self.documents))
                    else:
                        self.documents = []
                        self.timestamps = []
                        
                logger.info(f"Loaded {len(self.documents)} documents")
                # Initialize access order for loaded documents
                now = time.time()
                for i in range(len(self.documents)):
                    self.access_order[i] = now
            except Exception as e:
                logger.warning(f"Failed to load documents: {e}")
                self.documents = []
                self.timestamps = []
    
    def save(self):
        """Save FAISS index and documents to disk"""
        try:
            # Ensure directory exists
            self._ensure_data_dir()
            
            # Save FAISS index
            faiss.write_index(self.index, str(self.persist_path))
            
            # Save documents with metadata
            data = {
                'documents': self.documents,
                'timestamps': self.timestamps,
                'saved_at': time.time()
            }
            with open(self.docs_path, "wb") as f:
                pickle.dump(data, f)
            
            logger.info(f"Saved {self.index.ntotal} vectors and {len(self.documents)} documents")
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def _should_compress(self) -> bool:
        """Check if we should compress old memories"""
        return (self.compression_enabled and 
                len(self.documents) > self.compression_threshold)
    
    def _rebuild_index(self):
        """Rebuild the entire FAISS index from current documents"""
        if not self.documents:
            base = faiss.IndexFlatL2(self.d)
            self.index = faiss.IndexIDMap(base)
            self.access_order.clear()
            return
        
        vecs = model.encode(self.documents)
        if vecs.ndim == 1:
            vecs = vecs.reshape(1, -1)
        
        base = faiss.IndexFlatL2(self.d)
        new_index = faiss.IndexIDMap(base)
        ids = np.arange(len(self.documents), dtype=np.int64)
        new_index.add_with_ids(vecs, ids)
        self.index = new_index
        
        # Rebuild access_order with new indices
        new_access_order = OrderedDict()
        for i in range(len(self.documents)):
            new_access_order[i] = self.timestamps[i]
        self.access_order = new_access_order
    
    def _compress_old_memories(self):
        """Compress memories by removing less recently used ones"""
        if len(self.documents) <= self.max_memories // 2:
            return
            
        target_size = self.max_memories // 2
        if len(self.documents) <= target_size:
            return
        
        with self._lock:
            # Sort by access time (least recently used first)
            sorted_by_access = sorted(self.access_order.items(), key=lambda x: x[1])
            
            # Remove least recently used documents
            to_remove = len(self.documents) - target_size
            removed_indices = [idx for idx, _ in sorted_by_access[:to_remove]]
            
            # Remove from documents, timestamps, and access_order (in reverse order to maintain indices)
            for idx in sorted(removed_indices, reverse=True):
                self.documents.pop(idx)
                self.timestamps.pop(idx)
            
            # Rebuild index using helper method
            self._rebuild_index()
            logger.info(f"Compressed memory from {len(self.documents) + to_remove} to {len(self.documents)} documents")
    
    def add_memory(self, text: str, auto_save: bool = False) -> None:
        """Add memory to index with LRU eviction
        
        Args:
            text: Text to add
            auto_save: If False, caller manages saving (for batch operations)
        """
        if not text or len(text.strip()) == 0:
            logger.warning("add_memory called with empty text")
            return
        
        with self._lock:
            # Check if we need to evict old memories before adding
            if len(self.documents) >= self.max_memories:
                self._evict_lru()
            
            vec = model.encode([text])
            # Ensure 2D array (N, D) for FAISS
            if vec.ndim == 1:
                vec = vec.reshape(1, -1)
            
            # Resize index if dimension changed (only on first add or after clear)
            if self.index.ntotal == 0 and vec.shape[1] != self.d:
                base_index = faiss.IndexFlatL2(vec.shape[1])
                self.index = faiss.IndexIDMap(base_index)
                self.d = vec.shape[1]
            
            # Verify dimension matches before adding
            if vec.shape[1] != self.d:
                logger.warning(f"Dimension mismatch: {vec.shape[1]} vs {self.d}, skipping")
                return
            
            # Generate explicit ID for this document
            doc_id = len(self.documents)
            
            # Add to index with explicit ID and documents
            self.index.add_with_ids(vec, np.array([doc_id], dtype=np.int64))
            self.documents.append(text)
            self.timestamps.append(time.time())
            
            # Update access order (new item is most recently used)
            self.access_order[doc_id] = time.time()
            
            # Move to end of OrderedDict to mark as most recently used
            self.access_order.move_to_end(doc_id)
            
            logger.debug(f"FAISS index ntotal after add: {self.index.ntotal}")
            
            # Check if we should compress
            if self._should_compress():
                self._compress_old_memories()
            
            # Auto-save only if requested (disabled by default for performance)
            if auto_save:
                self.save()
    
    def _evict_lru(self):
        """Evict least recently used document - MUST be called with lock held"""
        if not self.access_order:
            return
            
        # Get least recently used item
        lru_key, _ = self.access_order.popitem(last=False)
        
        # Remove from documents and timestamps
        if 0 <= lru_key < len(self.documents):
            self.documents.pop(lru_key)
            self.timestamps.pop(lru_key)
            
            # Rebuild index using helper method
            self._rebuild_index()
            logger.debug(f"Evicted LRU document at index {lru_key}")
    
    def search(self, query: str, k: int = 3) -> list:
        """Search in memory with LRU update"""
        if not query or len(query.strip()) == 0:
            logger.warning("search_memory called with empty query")
            return []
        
        with self._lock:
            if self.index.ntotal == 0:
                logger.debug("Empty index - returning empty results")
                return []
            
            vec = model.encode([query])
            # Ensure 2D array (1, D)
            if vec.ndim == 1:
                vec = vec.reshape(1, -1)
            
            # Ensure vector dimension matches
            if vec.shape[1] != self.d:
                logger.warning(f"Vector dimension mismatch: {vec.shape[1]} vs {self.d}")
                return []
            
            try:
                # Search returns (distances, ids) for IndexIDMap
                D, I = self.index.search(vec, min(k, self.index.ntotal))
            except Exception as e:
                logger.error(f"Search error: {e}")
                return []
            
            results = []
            for idx, doc_id in enumerate(I[0]):
                if doc_id >= 0 and doc_id < len(self.documents):
                    # Update access time for LRU
                    if doc_id in self.access_order:
                        self.access_order[doc_id] = time.time()
                        self.access_order.move_to_end(doc_id)  # Mark as most recently used
                    
                    results.append({
                        "text": self.documents[doc_id],
                        "score": float(D[0][idx])  # Already L2 distance
                    })
            
            logger.debug(f"FAISS search results: count={len(results)}")
            return results
    
    def clear(self) -> None:
        """Clear all memory"""
        with self._lock:
            base = faiss.IndexFlatL2(self.d)
            self.index = faiss.IndexIDMap(base)
            self.documents = []
            self.timestamps = []
            self.access_order.clear()
            logger.info("Memory cleared")
            self.save()
    
    def count(self) -> int:
        """Get number of memories"""
        return self.index.ntotal
    
    def get_stats(self) -> dict:
        """Get memory statistics"""
        return {
            "total_memories": self.index.ntotal,
            "max_memories": self.max_memories,
            "memory_usage_percent": (self.index.ntotal / self.max_memories) * 100 if self.max_memories > 0 else 0,
            "compression_enabled": self.compression_enabled,
            "compression_threshold": self.compression_threshold
        }


# Singleton instance - thread-safe
_memory_manager: Optional[MemoryManager] = None
_memory_lock = threading.Lock()


def get_memory_manager() -> MemoryManager:
    """Get singleton memory manager (thread-safe)"""
    global _memory_manager
    if _memory_manager is None:
        with _memory_lock:
            if _memory_manager is None:
                _memory_manager = MemoryManager()
    return _memory_manager


# Backward compatibility - standalone functions
def add_memory(text: str) -> None:
    get_memory_manager().add_memory(text)


def search_memory(query: str, k: int = 3) -> list:
    return get_memory_manager().search(query, k)


# Simple logger object for tests
class MockLogger:
    def info(self, *args, **kwargs):
        pass
    def warning(self, *args, **kwargs):
        pass
    def debug(self, *args, **kwargs):
        pass
    def error(self, *args, **kwargs):
        pass


vectorizer = MockLogger()

