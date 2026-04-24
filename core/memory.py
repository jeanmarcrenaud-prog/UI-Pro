# memory.py
from .logger import get_logger
from pathlib import Path
import os
import pickle

# Suppress warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

logger = get_logger(__name__)

# Default config - will be loaded from config.py
DEFAULT_PERSIST_PATH = Path("data/memory.index")
DEFAULT_DOCS_PATH = Path("data/memory_docs.pkl")

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

logger.info("Memory module initialized")

# modèle pour embeddings
model = SentenceTransformer("all-MiniLM-L6-v2")

# Simple MemoryManager class with persistence
class MemoryManager:
    """Memory manager with FAISS index, TfidfVectorizer, and persistence"""
    
    def __init__(self, persist_path: str = None):
        # Default dimension
        self.d = 384
        self.index = faiss.IndexFlatL2(self.d)
        self.documents = []
        self.vectors = None
        self.vectorizer = None
        
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
                self.index = faiss.read_index(str(self.persist_path))
                # Sync dimension after loading
                if self.index.ntotal > 0:
                    self.d = self.index.d
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors, dim={self.d}")
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}")
                self.index = faiss.IndexFlatL2(self.d)
        
        if self.docs_path.exists():
            try:
                with open(self.docs_path, "rb") as f:
                    self.documents = pickle.load(f)
                logger.info(f"Loaded {len(self.documents)} documents")
            except Exception as e:
                logger.warning(f"Failed to load documents: {e}")
                self.documents = []
    
    def save(self):
        """Save FAISS index and documents to disk"""
        try:
            # Ensure directory exists
            self._ensure_data_dir()
            
            # Save FAISS index
            faiss.write_index(self.index, str(self.persist_path))
            
            # Save documents
            with open(self.docs_path, "wb") as f:
                pickle.dump(self.documents, f)
            
            logger.info(f"Saved {self.index.ntotal} vectors and {len(self.documents)} documents")
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def add_memory(self, text: str, auto_save: bool = False) -> None:
        """Add memory to index
        
        Args:
            text: Text to add
            auto_save: If False, caller manages saving (for batch operations)
        """
        if not text or len(text.strip()) == 0:
            logger.warning("add_memory called with empty text")
            return
        
        vec = model.encode([text])
        # Ensure 2D array (N, D) for FAISS
        if vec.ndim == 1:
            vec = vec.reshape(1, -1)
        
        # Resize index if dimension changed (only on first add or after clear)
        if self.index.ntotal == 0 and vec.shape[1] != self.d:
            self.index = faiss.IndexFlatL2(vec.shape[1])
            self.d = vec.shape[1]
        
        # Verify dimension matches before adding
        if vec.shape[1] != self.d:
            logger.warning(f"Dimension mismatch: {vec.shape[1]} vs {self.d}, skipping")
            return
        
        self.index.add(vec)
        self.documents.append(text)
        
        logger.debug(f"FAISS index ntotal after add: {self.index.ntotal}")
        
        # Auto-save only if requested (disabled by default for performance)
        if auto_save:
            self.save()
    
    def search(self, query: str, k: int = 3) -> list:
        """Search in memory"""
        if not query or len(query.strip()) == 0:
            logger.warning("search_memory called with empty query")
            return []
        
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
            D, I = self.index.search(vec, min(k, self.index.ntotal))
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
        
        results = []
        for idx, i in enumerate(I[0]):
            if i >= 0 and i < len(self.documents):
                results.append({
                    "text": self.documents[i],
                    "score": float(D[0][idx])  # Already L2 distance
                })
        
        logger.debug(f"FAISS search results: count={len(results)}")
        return results
    
    def clear(self) -> None:
        """Clear all memory"""
        self.index = faiss.IndexFlatL2(self.d)
        self.documents = []
        logger.info("Memory cleared")
        self.save()
    
    def count(self) -> int:
        """Get number of memories"""
        return self.index.ntotal


# Singleton instance - thread-safe
import threading

_memory_manager: MemoryManager = None
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

