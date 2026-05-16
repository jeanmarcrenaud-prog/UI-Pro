"""
Embedding Cache - LRU cache for text embeddings.
Single responsibility: cache embeddings with bounded size.
"""

from collections import OrderedDict
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from ..domain.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CACHE_SIZE = 2048


class EmbeddingCache:
    """LRU cache for embeddings with bounded size."""
    
    def __init__(self, max_size: int = DEFAULT_CACHE_SIZE):
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._lock = __import__('threading').Lock()
        self._max_size = max_size
    
    def get(self, text: str) -> Optional[np.ndarray]:
        """Get cached embedding (returns copy to avoid cache corruption)."""
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                return self._cache[text].copy()
        return None
    
    def put(self, text: str, embedding: np.ndarray) -> None:
        """Store embedding in cache."""
        with self._lock:
            if text not in self._cache:
                self._cache[text] = embedding.copy()
                while len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)
    
    def embed_single(self, text: str, model: SentenceTransformer) -> np.ndarray:
        """Get embedding from cache or compute and cache it."""
        cached = self.get(text)
        if cached is not None:
            return cached
        
        # Compute embedding (outside lock)
        embedding = model.encode(text)
        if hasattr(embedding, 'detach'):
            embedding = embedding.detach().cpu().numpy()
        embedding = np.asarray(embedding, dtype=np.float32)
        embedding = np.ascontiguousarray(embedding)
        
        self.put(text, embedding)
        return embedding.copy()
    
    def embed_batch(self, texts: List[str], model: SentenceTransformer) -> np.ndarray:
        """Batch embeddings with cache."""
        if not texts:
            return np.array([], dtype=np.float32)
        
        n = len(texts)
        result: List[Optional[np.ndarray]] = [None] * n
        uncached_texts: List[str] = []
        uncached_indices: List[int] = []
        
        # Check cache
        with self._lock:
            for i, text in enumerate(texts):
                if text in self._cache:
                    self._cache.move_to_end(text)
                    result[i] = self._cache[text].copy()
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)
        
        # Encode uncached
        if uncached_texts:
            embeddings = model.encode(uncached_texts, show_progress_bar=False)
            if hasattr(embeddings, 'detach'):
                embeddings = embeddings.detach().cpu().numpy()
            embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
            
            with self._lock:
                for idx, text, emb in zip(uncached_indices, uncached_texts, embeddings):
                    self._cache[text] = emb.copy()
                    while len(self._cache) > self._max_size:
                        self._cache.popitem(last=False)
            
            for idx, emb in zip(uncached_indices, embeddings):
                result[idx] = emb
        
        return np.stack([r for r in result if r is not None]).astype(np.float32)
    
    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
    
    @property
    def size(self) -> int:
        """Current cache size."""
        with self._lock:
            return len(self._cache)


# Module-level singleton cache
_cache: Optional[EmbeddingCache] = None
_cache_lock = __import__('threading').Lock()


def get_embedding_cache(max_size: int = DEFAULT_CACHE_SIZE) -> EmbeddingCache:
    """Get singleton embedding cache."""
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = EmbeddingCache(max_size)
    return _cache