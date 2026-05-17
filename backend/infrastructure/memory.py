"""
backend/infrastructure/memory.py - Vector Store Only
Pure FAISS vector store - no metadata persistence.
MemoryService is the source of truth for rich metadata.
"""

from __future__ import annotations

import atexit
import signal
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from .embedding_cache import EmbeddingCache, get_embedding_cache
from .vector_index import VectorIndex
from ..domain.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_PERSIST_PATH = Path("data/memory.index")


# Re-export for backward compatibility
class MockLogger:
    """Mock logger for testing purposes."""
    def debug(self, msg, *args, **kwargs):
        pass
    def info(self, msg, *args, **kwargs):
        pass
    def warning(self, msg, *args, **kwargs):
        pass
    def error(self, msg, *args, **kwargs):
        pass
    def critical(self, msg, *args, **kwargs):
        pass


class MemoryManager:
    """Pure vector store - FAISS index only, no metadata.
    
    MemoryService manages rich metadata (_entries) as source of truth.
    This class only handles vector operations and search.
    """
    
    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self, persist_path: Optional[str] = None, max_memories: int = 1000):
        self._lock = threading.RLock()

        self.persist_path = Path(persist_path or DEFAULT_PERSIST_PATH)

        self.dimension = 384
        self.max_memories = max_memories

        # Dependencies
        self._vector_index = VectorIndex(self.dimension)
        self._embed_cache = get_embedding_cache()
        
        # Simple tracking (no persistence needed - MemoryService handles metadata)
        self._next_id: int = 0
        self._version: int = 0

        self._model: Optional[SentenceTransformer] = None
        self._model_lock = threading.Lock()

        self.persist_path.parent.mkdir(parents=True, exist_ok=True)

        # Register shutdown handlers
        atexit.register(self._shutdown)
        if hasattr(signal, 'SIGTERM'):
            try:
                signal.signal(signal.SIGTERM, self._signal_handler)
            except (ValueError, OSError):
                pass

        self._load()

    def _signal_handler(self, signum, frame):
        self._vector_index.save(str(self.persist_path))

    def _shutdown(self):
        try:
            self._vector_index.save(str(self.persist_path))
        except Exception as e:
            logger.error(f"Shutdown persistence failed: {e}")

    # ====================== MODEL (Lazy Loading) ======================
    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    logger.info(f"Loading embedding model: {self.MODEL_NAME}")
                    self._model = SentenceTransformer(self.MODEL_NAME)
        return self._model

    # ====================== EMBEDDINGS ======================
    def embed(self, text: str) -> np.ndarray:
        return self._embed_cache.embed_single(text, self.model)

    def embed_many(self, texts: List[str]) -> np.ndarray:
        return self._embed_cache.embed_batch(texts, self.model)

    # ====================== CORE OPERATIONS ======================
    def add_vector(self, embedding: np.ndarray) -> int:
        """Add a vector and return its ID."""
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)
        
        faiss.normalize_L2(embedding)
        vector = np.ascontiguousarray(embedding, dtype=np.float32)

        with self._lock:
            doc_id = self._next_id
            self._next_id += 1
            ids = np.ascontiguousarray(np.array([doc_id]), dtype=np.int64)

            self._vector_index.add_vectors(vector, ids)
            self._version += 1
            
            return doc_id

    def add_text(self, text: str) -> int:
        """Add text - computes embedding and stores vector."""
        embedding = self.embed(text)
        return self.add_vector(embedding)

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search vectors and return results with scores."""
        embedding = self.embed(query)
        
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)
        
        faiss.normalize_L2(embedding)
        query_vector = np.ascontiguousarray(embedding, dtype=np.float32)
        
        with self._lock:
            size = self._vector_index.ntotal
            if size == 0:
                return []
            
            vector_index = self._vector_index

        k = min(int(limit), size)
        distances, labels = vector_index.search(query_vector, k)

        results = []
        for i, doc_id in enumerate(labels[0]):
            if doc_id < 0:
                continue
            
            squared_l2 = float(distances[0][i])
            similarity = max(0, 1.0 - (squared_l2 / 2.0))

            results.append({
                "id": int(doc_id),
                "score": squared_l2,
                "similarity": similarity,
            })

        return results

    def rebuild_from_arrays(self, vectors: np.ndarray, ids: np.ndarray) -> None:
        """Rebuild index from arrays (for MemoryService sync)."""
        new_index = VectorIndex(self.dimension)
        new_index.rebuild_from_vectors(vectors, ids)
        
        with self._lock:
            self._vector_index = new_index
            self._next_id = int(max(ids)) + 1 if len(ids) > 0 else 0
            self._version += 1

    # ====================== PERSISTENCE ======================
    def save(self):
        """Save index to disk."""
        self._vector_index.save(str(self.persist_path))

    # ====================== LOAD ======================
    def _load(self):
        """Load vector index from disk."""
        if self.persist_path.exists():
            if not self._vector_index.load(str(self.persist_path)):
                logger.warning("Recreating index due to load failure")
            else:
                logger.info(f"Loaded index with {self._vector_index.ntotal} vectors")

    # ====================== STATS ======================
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_vectors": self._vector_index.ntotal,
                "max_memories": self.max_memories,
                "next_id": self._next_id,
                "version": self._version,
            }

    def clear(self) -> None:
        """Clear the index."""
        with self._lock:
            self._vector_index = VectorIndex(self.dimension)
            self._next_id = 0
            self._version += 1
            self.save()
            logger.info("Vector index cleared")


# ====================== SINGLETON ======================

_memory_manager: Optional[MemoryManager] = None
_memory_lock = threading.Lock()


def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        with _memory_lock:
            if _memory_manager is None:
                _memory_manager = MemoryManager()
    return _memory_manager


# ====================== Legacy Functions ======================

def add_memory(text: str) -> int:
    """Add memory - returns vector ID."""
    return get_memory_manager().add_text(text)


def search_memory(query: str, k: int = 3) -> list:
    return get_memory_manager().search(query, k)


class _ModelProxy:
    def __getattr__(self, name):
        return getattr(get_memory_manager().model, name)


model = _ModelProxy()