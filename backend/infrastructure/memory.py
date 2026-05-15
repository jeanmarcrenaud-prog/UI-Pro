"""
backend/infrastructure/memory.py - FAISS Memory Store
Memory manager optimisé avec lazy loading, locks thread-safe
et cache embeddings.
"""

from __future__ import annotations

import hashlib
import os
import pickle
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, cast, Tuple
import torch
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from ..domain.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_PERSIST_PATH = Path("data/memory.index")
DEFAULT_DOCS_PATH = Path("data/memory_docs.pkl")

class MemoryManager:
    MODEL_NAME = "all-MiniLM-L6-v2"
    PERSIST_EVERY = 5  # Persist every N additions

    def __init__(self, persist_path: Optional[str] = None, max_memories: int = 1000):
        self._lock = threading.RLock()

        self.persist_path = Path(persist_path or DEFAULT_PERSIST_PATH)
        self.docs_path = DEFAULT_DOCS_PATH

        self.dimension = 384
        self.max_memories = max_memories

        base = faiss.IndexFlatL2(self.dimension)
        self.index = faiss.IndexIDMap(base)

        self.documents: List[Dict[str, Any]] = []
        self.access_order = OrderedDict()

        self._model: Optional[SentenceTransformer] = None
        self._dirty = False  # Track unsaved changes
        self._add_count = 0  # Counter for batch persist

        self.persist_path.parent.mkdir(parents=True, exist_ok=True)

        self._load()

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("loading embedding model")
            self._model = SentenceTransformer(self.MODEL_NAME)

        return self._model

    @lru_cache(maxsize=2048)
    def _cached_embedding(self, text_hash: str, text: str):
        embedding = self.model.encode(text)
        if isinstance(embedding, torch.Tensor):
            embedding = embedding.detach().cpu().numpy()
        return np.asarray(embedding, dtype=np.float32)

    def embed(self, text: str) -> np.ndarray:
        """Embed text with caching using MD5 hash."""
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:16]
        return self._cached_embedding(text_hash, text)

    def add_memory(self, text: str, metadata: Optional[Dict[str, Any]] = None):
        with self._lock:
            # Check if we need to prune first
            if len(self.documents) >= self.max_memories:
                self._prune_oldest()

            # Compute embedding once (cached)
            embedding = self.embed(text)
            vector = np.array([embedding], dtype=np.float32)

            idx = len(self.documents)
            ids = np.array([idx], dtype=np.int64)

            # Add to existing index (NOT recreate!)
            self.index.add_with_ids(vector, ids)

            # Store embedding in document for fast rebuild
            self.documents.append(
                {
                    "text": text,
                    "embedding": embedding.tolist(),  # Store for fast rebuild
                    "metadata": metadata or {},
                    "created_at": time.time(),
                    "last_access": time.time(),
                }
            )

            self.access_order[idx] = time.time()

            # Bufferize persist - only persist every N additions
            self._dirty = True
            self._add_count += 1
            if self._add_count >= self.PERSIST_EVERY:
                self._persist()
                self._add_count = 0

    def search(self, query: str, limit: int = 5):
        with self._lock:
            if not self.documents:
                return []

            # Compute query embedding once
            query_vector = np.array([self.embed(query)], dtype=np.float32)
            k = min(int(limit), len(self.documents))

            # Search the index
            distances, labels = self.index.search(query_vector, k)

            results = []
            for i, doc_id in enumerate(labels[0]):
                if doc_id >= 0 and doc_id < len(self.documents):
                    doc = self.documents[doc_id]
                    distance = float(distances[0][i])

                    # Update access time
                    doc["last_access"] = time.time()
                    self.access_order[doc_id] = time.time()

                    results.append({
                        "text": doc["text"],
                        "metadata": doc.get("metadata", {}),
                        "score": distance,
                        "similarity": 1.0 / (1.0 + distance),  # More intuitive: higher = better
                    })

            return results

    def _persist(self):
        """Persist index and documents to disk."""
        if not self._dirty:
            return
        faiss.write_index(self.index, str(self.persist_path))

        with open(self.docs_path, "wb") as f:
            pickle.dump(self.documents, f)

        self._dirty = False
        logger.debug(f"Persisted {len(self.documents)} memories")

    def save(self):
        """Public method for external persistence."""
        self._persist()

    def _load(self):
        """Load index and documents from disk with type checking."""
        if self.persist_path.exists():
            try:
                loaded_index = faiss.read_index(str(self.persist_path))
                if isinstance(loaded_index, faiss.IndexIDMap):
                    self.index = loaded_index
                    logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
                else:
                    logger.warning("Index type mismatch, recreating IndexIDMap...")
                    base = faiss.IndexFlatL2(self.dimension)
                    self.index = faiss.IndexIDMap(base)
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}")
                base = faiss.IndexFlatL2(self.dimension)
                self.index = faiss.IndexIDMap(base)

        if self.docs_path.exists():
            try:
                with open(self.docs_path, "rb") as f:
                    self.documents = pickle.load(f)
                logger.info(f"Loaded {len(self.documents)} documents")
                # Rebuild access_order
                for i, doc in enumerate(self.documents):
                    self.access_order[i] = doc.get("last_access", doc.get("created_at", time.time()))
            except Exception as e:
                logger.warning(f"Failed to load documents: {e}")
                self.documents = []

    def _prune_oldest(self):
        """Remove oldest memories when max is reached."""
        current_size = len(self.documents)
        if current_size <= self.max_memories // 2:
            return

        target_size = self.max_memories // 2
        to_remove_count = current_size - target_size

        # Sort by access time (least recently used first)
        sorted_items = sorted(self.access_order.items(), key=lambda x: x[1])
        indices_to_remove = [idx for idx, _ in sorted_items[:to_remove_count]]
        indices_to_remove = sorted(indices_to_remove, reverse=True)  # pop from end

        for idx in indices_to_remove:
            self.documents.pop(idx)
            self.access_order.pop(idx, None)

        # Rebuild index
        self._rebuild_index()
        logger.info(f"Pruned {to_remove_count} memories → {len(self.documents)} kept")

    def _rebuild_index(self):
        """Rebuild FAISS index from current documents using stored embeddings."""
        if not self.documents:
            base = faiss.IndexFlatL2(self.dimension)
            self.index = faiss.IndexIDMap(base)
            return

        # Use stored embeddings (much faster than re-embedding)
        vectors = np.array([doc["embedding"] for doc in self.documents], dtype=np.float32)
        ids = np.arange(len(self.documents), dtype=np.int64)

        base = faiss.IndexFlatL2(self.dimension)
        self.index = faiss.IndexIDMap(base)
        self.index.add_with_ids(vectors, ids)

        # Rebuild access_order with new indices
        self.access_order = OrderedDict((i, doc.get("last_access", time.time())) for i, doc in enumerate(self.documents))

    def get_stats(self) -> Dict[str, Any]:
        """Return memory statistics."""
        with self._lock:
            return {
                "total_memories": len(self.documents),
                "index_vectors": self.index.ntotal,
                "max_memories": self.max_memories,
                "usage_percent": (len(self.documents) / self.max_memories * 100) if self.max_memories > 0 else 0,
                "dirty": self._dirty,
                "pending_persists": self._add_count,
            }

    def clear(self) -> None:
        """Clear all memories."""
        with self._lock:
            base = faiss.IndexFlatL2(self.dimension)
            self.index = faiss.IndexIDMap(base)
            self.documents = []
            self.access_order.clear()
            self._dirty = True
            self._persist()
            logger.info("Memory cleared")


# ====================== Singleton (Backward Compatibility) ======================

_memory_manager: Optional[MemoryManager] = None
_memory_lock = threading.Lock()


def get_memory_manager() -> MemoryManager:
    """Get singleton memory manager (thread-safe)."""
    global _memory_manager
    if _memory_manager is None:
        with _memory_lock:
            if _memory_manager is None:
                _memory_manager = MemoryManager()
    return _memory_manager


# ====================== Standalone Functions (Backward Compatibility) ======================

def add_memory(text: str) -> None:
    """Add memory (legacy function)."""
    get_memory_manager().add_memory(text)


def search_memory(query: str, k: int = 3) -> list:
    """Search memory (legacy function)."""
    return get_memory_manager().search(query, k)


class MockLogger:
    """Mock logger for backward compatibility."""
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


# Module-level model for backward compatibility (lazy loaded)
class _ModelProxy:
    """Lazy proxy for model property."""
    def __getattr__(self, name):
        return getattr(get_memory_manager().model, name)


model = _ModelProxy()