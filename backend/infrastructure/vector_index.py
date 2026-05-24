"""
Vector Index - FAISS wrapper for vector storage and search.
Single responsibility: manage FAISS index with custom IDs.
"""

import faiss
import numpy as np

from ..domain.core.logger import get_logger

logger = get_logger(__name__)


class VectorIndex:
    """FAISS index wrapper with IDMap support."""

    def __init__(self, dimension: int = 384, hnsw_m: int = 32):
        self.dimension = dimension
        self.hnsw_m = hnsw_m

        # Create HNSW index
        base_index = faiss.IndexHNSWFlat(dimension, hnsw_m)
        base_index.hnsw.efConstruction = 200
        base_index.hnsw.efSearch = 50

        # Wrap with IndexIDMap for custom IDs
        self._index = faiss.IndexIDMap2(base_index)

    @property
    def ntotal(self) -> int:
        """Number of vectors in index."""
        return self._index.ntotal

    def add_vectors(self, vectors: np.ndarray, ids: np.ndarray) -> None:
        """Add vectors with custom IDs."""
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        ids = np.ascontiguousarray(ids, dtype=np.int64)
        self._index.add_with_ids(vectors, ids)  # type: ignore[call-arg]

    def search(self, query: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        """Search for k nearest neighbors."""
        query = np.ascontiguousarray(query, dtype=np.float32)
        return self._index.search(query, k)  # type: ignore[assignment]

    def rebuild_from_vectors(self, vectors: np.ndarray, ids: np.ndarray) -> None:
        """Rebuild index from vectors and IDs."""
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        ids = np.ascontiguousarray(ids, dtype=np.int64)

        # Create new index
        base_index = faiss.IndexHNSWFlat(self.dimension, self.hnsw_m)
        base_index.hnsw.efConstruction = 200
        base_index.hnsw.efSearch = 50
        self._index = faiss.IndexIDMap2(base_index)
        self._index.add_with_ids(vectors, ids)  # type: ignore[call-arg]

    def clear(self) -> None:
        """Clear the index."""
        base_index = faiss.IndexHNSWFlat(self.dimension, self.hnsw_m)
        base_index.hnsw.efConstruction = 200
        base_index.hnsw.efSearch = 50
        self._index = faiss.IndexIDMap2(base_index)

    def save(self, path: str) -> None:
        """Save index to file."""
        faiss.write_index(self._index, path)

    def load(self, path: str) -> bool:
        """Load index from file. Returns True if successful."""
        try:
            loaded = faiss.read_index(path)
            if hasattr(loaded, "id_map"):
                self._index = loaded
                return True
            else:
                logger.warning("Loaded index is not IDMap type")
                return False
        except Exception as e:
            logger.warning(f"Failed to load index: {e}")
            return False

    @property
    def index(self) -> faiss.Index:
        """Get the underlying FAISS index (for internal use)."""
        return self._index
