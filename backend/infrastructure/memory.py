"""
backend/infrastructure/memory.py - Memory Store Orchestrator
Coordinates EmbeddingCache and VectorIndex for complete memory management.
Single responsibility: orchestrate memory operations.
"""

from __future__ import annotations

import atexit
import pickle
import signal
import threading
import time
from collections import OrderedDict
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


class MemoryManager:
    """Memory store orchestrator - coordinates embedding cache and vector index."""
    
    MODEL_NAME = "all-MiniLM-L6-v2"
    PERSIST_EVERY = 5  # Persist every N additions

    def __init__(self, persist_path: Optional[str] = None, max_memories: int = 1000):
        self._lock = threading.RLock()

        self.persist_path = Path(persist_path or DEFAULT_PERSIST_PATH)
        self.docs_path = self.persist_path.parent / "memory_docs.pkl"

        self.dimension = 384
        self.max_memories = max_memories

        # Dependencies (injected for testability)
        self._vector_index = VectorIndex(self.dimension)
        self._embed_cache = get_embedding_cache()
        
        # Document storage
        self._doc_map: Dict[int, Dict[str, Any]] = {}
        self._access_order: OrderedDict[int, None] = OrderedDict()
        self._next_id: int = 0
        self._version: int = 0

        self._model: Optional[SentenceTransformer] = None
        self._model_lock = threading.Lock()
        self._dirty = False
        self._add_count = 0

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
        self._persist()

    def _shutdown(self):
        try:
            self._persist()
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
    def add_memory(self, text: str, metadata: Optional[Dict[str, Any]] = None):
        # Compute embedding outside lock
        embedding = self.embed(text)
        
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)
        
        faiss.normalize_L2(embedding)
        
        with self._lock:
            if len(self._doc_map) >= self.max_memories:
                self._prune_oldest()

            vector = np.ascontiguousarray(embedding, dtype=np.float32)

            doc_id = self._next_id
            self._next_id += 1
            ids = np.ascontiguousarray(np.array([doc_id]), dtype=np.int64)

            # Add to vector index
            self._vector_index.add_vectors(vector, ids)

            # Store document
            self._doc_map[doc_id] = {
                "text": text,
                "embedding": embedding.tobytes(),
                "normalized": True,
                "metadata": metadata or {},
                "created_at": time.time(),
            }

            # Update LRU
            self._access_order[doc_id] = None
            self._access_order.move_to_end(doc_id)

            self._dirty = True
            self._add_count += 1
            if self._add_count >= self.PERSIST_EVERY:
                self._persist()
                self._add_count = 0

    def search(self, query: str, limit: int = 5):
        embedding = self.embed(query)
        
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)
        
        faiss.normalize_L2(embedding)
        query_vector = np.ascontiguousarray(embedding, dtype=np.float32)
        
        with self._lock:
            if not self._doc_map:
                return []
            
            doc_map_ref = dict(self._doc_map)
            valid_ids = set(doc_map_ref.keys())
            version = self._version
            size = len(doc_map_ref)
            vector_index = self._vector_index

        k = min(int(limit), size)
        distances, labels = vector_index.search(query_vector, k)

        results = []
        for i, doc_id in enumerate(labels[0]):
            if doc_id < 0 or doc_id not in valid_ids:
                continue
            
            doc = doc_map_ref.get(doc_id)
            if not doc:
                continue
            
            squared_l2 = float(distances[0][i])
            similarity = max(0, 1.0 - (squared_l2 / 2.0))

            results.append({
                "text": doc["text"],
                "metadata": doc.get("metadata", {}),
                "score": squared_l2,
                "similarity": similarity,
            })

        return results

    # ====================== PERSISTENCE ======================
    def _persist(self):
        if not self._dirty:
            return

        with self._lock:
            if not self._dirty:
                return

            expected_count = len(self._doc_map)
            actual_count = self._vector_index.ntotal
            
            if expected_count != actual_count:
                logger.warning(f"Index count mismatch: {actual_count} vs {expected_count}")
                self._dirty = True

            if __debug__:
                for doc_id in self._doc_map:
                    assert doc_id >= 0, f"Invalid doc_id: {doc_id}"

            try:
                tmp_index = self.persist_path.with_suffix('.tmp')
                tmp_docs = self.docs_path.with_suffix('.tmp')

                self._vector_index.save(str(tmp_index))

                with open(tmp_docs, "wb") as f:
                    pickle.dump(self._doc_map, f)

                tmp_index.replace(self.persist_path)
                tmp_docs.replace(self.docs_path)

                self._dirty = False
                logger.debug(f"Persisted {len(self._doc_map)} memories")

            except Exception as e:
                logger.error(f"Persistence failed: {e}")
                tmp_index = self.persist_path.with_suffix('.tmp')
                tmp_docs = self.docs_path.with_suffix('.tmp')
                tmp_index.unlink(missing_ok=True)
                tmp_docs.unlink(missing_ok=True)

    def save(self):
        self._persist()

    # ====================== LOAD ======================
    def _load(self):
        # Load vector index
        if self.persist_path.exists():
            if not self._vector_index.load(str(self.persist_path)):
                logger.warning("Recreating index due to load failure")

        # Load documents
        if self.docs_path.exists():
            try:
                with open(self.docs_path, "rb") as f:
                    self._doc_map = pickle.load(f)
                
                for doc_id in self._doc_map.keys():
                    self._access_order[doc_id] = None
                
                max_id = max(self._doc_map.keys(), default=-1)
                self._next_id = max_id + 1
                self._version = 0
                logger.info(f"Loaded {len(self._doc_map)} documents, next_id={self._next_id}")
            except Exception as e:
                logger.warning(f"Failed to load documents: {e}")
                self._doc_map = {}

    # ====================== PRUNING ======================
    def _prune_oldest(self):
        current_size = len(self._doc_map)
        if current_size <= self.max_memories // 2:
            return

        target_size = self.max_memories // 2
        to_remove_count = current_size - target_size
        ids_to_remove = list(self._access_order)[:to_remove_count]

        for doc_id in ids_to_remove:
            self._doc_map.pop(doc_id, None)
            self._access_order.pop(doc_id, None)

        self._rebuild_index()

        self._dirty = True
        logger.info(f"Pruned {to_remove_count} memories -> {len(self._doc_map)} kept")

    # ====================== REBUILD ======================
    def _rebuild_index(self):
        new_index = self._build_new_index()
        
        with self._lock:
            self._vector_index = new_index
            self._version += 1

    def _build_new_index(self) -> VectorIndex:
        if not self._doc_map:
            return VectorIndex(self.dimension)

        vectors = np.stack([
            np.frombuffer(doc["embedding"], dtype=np.float32)
            for doc in self._doc_map.values()
        ])
        
        ids = list(self._doc_map.keys())

        assert len(ids) == len(self._doc_map)
        assert len(set(ids)) == len(ids)
        assert all(doc_id >= 0 for doc_id in ids)

        ids_arr = np.ascontiguousarray(ids, dtype=np.int64)

        new_index = VectorIndex(self.dimension)
        new_index.rebuild_from_vectors(vectors, ids_arr)

        max_id = max(self._doc_map.keys(), default=-1)
        self._next_id = max_id + 1
        
        return new_index

    # ====================== STATS ======================
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_memories": len(self._doc_map),
                "index_vectors": self._vector_index.ntotal,
                "max_memories": self.max_memories,
                "usage_percent": (len(self._doc_map) / self.max_memories * 100) if self.max_memories > 0 else 0,
                "dirty": self._dirty,
                "pending_persists": self._add_count,
                "next_id": self._next_id,
                "version": self._version,
            }

    def clear(self) -> None:
        with self._lock:
            self._vector_index = VectorIndex(self.dimension)
            self._doc_map.clear()
            self._access_order.clear()
            self._next_id = 0
            self._version += 1
            self._dirty = True
            self._persist()
            logger.info("Memory cleared")


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

def add_memory(text: str) -> None:
    get_memory_manager().add_memory(text)


def search_memory(query: str, k: int = 3) -> list:
    return get_memory_manager().search(query, k)


class _ModelProxy:
    def __getattr__(self, name):
        return getattr(get_memory_manager().model, name)


model = _ModelProxy()