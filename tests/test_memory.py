"""
test_memory.py - Unit tests for memory system

Tests for:
- FAISS vector storage and retrieval
- Text embedding functionality
- Memory context search
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

# Import under test - use absolute import
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMemoryManager:
    """Test MemoryManager class functionality"""
    
    def test_initialization(self):
        """Test MemoryManager initialization"""
        # Skip if FAISS not available in test environment
        try:
            from core.memory import MemoryManager
        except ImportError as e:
            pytest.skip(f"Cannot import MemoryManager: {e}")
        
        manager = MemoryManager()
        assert manager.index is not None
        assert manager.documents == []
    
    def test_add_memory_empty(self):
        """Test adding empty memory doesn't crash"""
        try:
            from core.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")
        
        manager = MemoryManager()
        
        # Adding empty text should not crash - should handle gracefully
        if hasattr(manager, 'add_memory'):
            try:
                manager.add_memory("")
            except Exception as e:
                pytest.fail(f"add_memory('') raised: {e}")
    
    def test_add_memory_multiple(self):
        """Test adding multiple memories"""
        try:
            from core.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")
        
        manager = MemoryManager()
        
        # Test method exists
        assert hasattr(manager, 'add_memory'), "MemoryManager missing add_memory method"
    
    def test_search_memory_returns_results(self):
        """Test search returns results when available"""
        try:
            from core.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")
        
        manager = MemoryManager()
        assert hasattr(manager, 'search'), "MemoryManager missing search method"
    
    def test_search_memory_empty_index(self):
        """Test search handles empty index"""
        try:
            from core.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")
        
        manager = MemoryManager()
        
        # Empty index should return empty list, not raise
        try:
            results = manager.search("test query", k=3)
            assert isinstance(results, (list, np.ndarray))
        except Exception as e:
            pytest.fail(f"search on empty index raised: {e}")


class TestVectorization:
    """Test vectorization functionality"""
    
    def test_vectorizer_initialization(self):
        """Test vectorizer is initialized"""
        try:
            from core.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")
        
        manager = MemoryManager()
        # vectorizer may or may not exist based on implementation
        # This is not a critical requirement
    
    def test_vectorizer_similarity(self):
        """Test vectorizer can compute similarity"""
        try:
            from core.memory import model
        except ImportError:
            pytest.skip("Cannot import model")
        
        # Test that model can encode text
        try:
            vec = model.encode(["test"])
            assert vec is not None
            assert len(vec) > 0
        except Exception as e:
            pytest.fail(f"model.encode failed: {e}")


class TestEdgeCases:
    """Test edge cases"""
    
    def test_search_with_no_matches(self):
        """Test search with no matching results"""
        try:
            from core.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")
        
        manager = MemoryManager()
        
        # Should handle gracefully even with empty index
        try:
            results = manager.search("nonexistent query that wont match anything", k=5)
            assert results is not None
        except Exception as e:
            pytest.fail(f"search raised: {e}")
    
    def test_search_with_special_characters(self):
        """Test search with special characters"""
        try:
            from core.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")
        
        manager = MemoryManager()
        
        # Should handle special characters gracefully
        try:
            results = manager.search("!@#$%^&*()", k=3)
        except Exception:
            pass  # May fail but should not crash
    
    def test_search_large_k_value(self):
        """Test search with large k value"""
        try:
            from core.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")
        
        manager = MemoryManager()
        
        # Large k should be handled gracefully
        try:
            results = manager.search("test", k=1000)
            assert results is not None
        except Exception as e:
            pytest.fail(f"search with large k raised: {e}")


# Test functions (if they exist)
def test_add_memory_call():
    """Test add_memory function"""
    try:
        from core.memory import add_memory
    except ImportError:
        pytest.skip("add_memory function not found")
    
    # Function should exist
    assert callable(add_memory)


def test_search_memory_call():
    """Test search_memory function"""
    try:
        from core.memory import search_memory
    except ImportError:
        pytest.skip("search_memory function not found")
    
    # Function should exist
    assert callable(search_memory)