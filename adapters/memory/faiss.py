# adapters/memory/faiss.py - FAISS Memory Adapter
#
# Wrapper for FAISS-based vector memory.

import logging
import os
from pathlib import Path
from typing import Optional, List, Dict
import pickle

# Suppress warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

logger = logging.getLogger(__name__)

# Lazy imports
faiss = None
np = None
SentenceTransformer = None


def _lazy_imports():
    global faiss, np, SentenceTransformer
    if faiss is None:
        import faiss
        import numpy as np
        from sentence_transformers import SentenceTransformer
    return faiss, np, SentenceTransformer


DEFAULT_PERSIST_PATH = Path("data/memory.index")
DEFAULT_DOCS_PATH = Path("data/memory_docs.pkl")


class FAISSAdapter:
    """
    FAISS-based memory adapter.
    
    Features:
    - Vector search with embeddings
    - Persistence to disk
    - Configurable dimension
    """
    
    def __init__(self, persist_path: str = None, dimension: int = 384):
        self.d = dimension
        self.index = None
        self.documents: List[str] = []
        
        # Paths
        self.persist_path = Path(persist_path or os.getenv("MEMORY_PERSIST_PATH", str(DEFAULT_PERSIST_PATH)))
        self.docs_path = Path(os.getenv("MEMORY_DOCS_PATH", str(DEFAULT_DOCS_PATH)))
        
        # Lazy load model
        self._model = None
        
        self._ensure_data_dir()
        self._load()
    
    def _ensure_data_dir(self):
        """Create data directory if needed"""
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
    
    @property
    def model(self):
        """Lazy load embedding model"""
        if self._model is None:
            f, _, st = _lazy_imports()
            self._model = st.SentenceTransformer("all-MiniLM-L6-v2")
            self.d = self._model.get_sentence_embedding_dimension()
            if self.index is None:
                self.index = f.IndexFlatL2(self.d)
        return self._model
    
    def _load(self):
        """Load existing index and documents"""
        if self.persist_path.exists():
            try:
                f, n, st = _lazy_imports()
                self.index = f.read_index(str(self.persist_path))
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}")
                self.index = f.IndexFlatL2(self.d)
        
        if self.docs_path.exists():
            try:
                with open(self.docs_path, "rb") as f:
                    self.documents = pickle.load(f)
                logger.info(f"Loaded {len(self.documents)} documents")
            except Exception as e:
                logger.warning(f"Failed to load documents: {e}")
                self.documents = []
    
    def save(self):
        """Save index and documents to disk"""
        try:
            self._ensure_data_dir()
            f, _, _ = _lazy_imports()
            f.write_index(self.index, str(self.persist_path))
            with open(self.docs_path, "wb") as f:
                pickle.dump(self.documents, f)
            logger.info(f"Saved {self.index.ntotal} vectors and {len(self.documents)} documents")
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def add(self, text: str):
        """Add text to memory"""
        if not text or not text.strip():
            return
        
        vec = self.model.encode([text])
        vec = vec[0].flatten()
        
        if self.index.ntotal == 0:
            f, _, _ = _lazy_imports()
            self.index = f.IndexFlatL2(vec.shape[0])
            self.d = vec.shape[0]
        
        self.index.add(vec)
        self.documents.append(text)
        self.save()
    
    def search(self, query: str, k: int = 3) -> List[Dict]:
        """Search memory for similar texts"""
        if not query or self.index.ntotal == 0:
            return []
        
        vec = self.model.encode([query])
        
        try:
            f, np, _ = _lazy_imports()
            D, I = self.index.search(vec.flatten().reshape(1, -1), min(k, self.index.ntotal))
            
            results = []
            for i in I[0]:
                if i >= 0 and i < len(self.documents):
                    results.append({
                        "text": self.documents[i],
                        "score": float(np.sqrt(D[0][list(I[0]).index(i)]))
                    })
            return results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def count(self) -> int:
        """Get number of stored memories"""
        return self.index.ntotal if self.index else 0
    
    def clear(self):
        """Clear all memories"""
        f, _, _ = _lazy_imports()
        self.index = f.IndexFlatL2(self.d)
        self.documents = []
        self.save()


__all__ = ["FAISSAdapter"]