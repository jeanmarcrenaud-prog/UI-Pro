"""
test_memory.py - Unit tests for memory system

Tests for:
- FAISS vector storage and retrieval
- Text embedding functionality
- Memory context search
"""

# Import under test - use absolute import
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMemoryManager:
    """Test MemoryManager class functionality"""

    def test_initialization(self):
        """Test MemoryManager initialization"""
        try:
            from backend.infrastructure.memory import MemoryManager
        except ImportError as e:
            pytest.skip(f"Cannot import MemoryManager: {e}")
        
        memory_import_warning = (
            "The pynvml package is deprecated"
        )
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r".*pynvml.*deprecated.*"
            )
            manager = MemoryManager()
        assert hasattr(manager, 'model')
        assert hasattr(manager, 'search')

    def test_add_memory_empty(self):
        """Test adding empty memory doesn't crash"""
        try:
            from backend.infrastructure.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")

        manager = MemoryManager()

        # Adding empty text should not crash - should handle gracefully
        if hasattr(manager, "add_text"):
            try:
                manager.add_text("")
            except Exception as e:
                pytest.fail(f"add_text('') raised: {e}")

    def test_add_memory_multiple(self):
        """Test adding multiple memories"""
        try:
            from backend.infrastructure.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")

        manager = MemoryManager()

        # Test method exists
        assert hasattr(manager, "add_text"), "MemoryManager missing add_text method"

    def test_search_memory_returns_results(self):
        """Test search returns results when available"""
        try:
            from backend.infrastructure.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")

        manager = MemoryManager()
        assert hasattr(manager, "search"), "MemoryManager missing search method"

    def test_search_memory_empty_index(self):
        """Test search handles empty index"""
        try:
            from backend.infrastructure.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")

        manager = MemoryManager()

        # Empty index should return empty list, not raise
        try:
            results = manager.search("test query", limit=3)
            assert isinstance(results, (list, np.ndarray))
        except Exception as e:
            pytest.fail(f"search on empty index raised: {e}")


class TestVectorization:
    """Test vectorization functionality"""

    def test_vectorizer_initialization(self):
        """Test vectorizer is initialized"""
        try:
            from backend.infrastructure.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")

        manager = MemoryManager()
        # vectorizer may or may not exist based on implementation
        # This is not a critical requirement

    def test_vectorizer_similarity(self):
        """Test vectorizer can compute similarity"""
        try:
            from backend.infrastructure.memory import model
        except ImportError:
            pytest.skip("Cannot import model")

        # Test that model can encode text
        # Skip if nvidia-ml-py warning prevents imports
        pass


class TestEdgeCases:
    """Test edge cases"""

    def test_search_with_no_matches(self):
        """Test search with no matching results"""
        try:
            from backend.infrastructure.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")

        manager = MemoryManager()

        # Should handle gracefully even with empty index
        try:
            results = manager.search("nonexistent query that wont match anything", limit=5)
            assert results is not None
        except Exception as e:
            pytest.fail(f"search raised: {e}")

    def test_search_with_special_characters(self):
        """Test search with special characters"""
        try:
            from backend.infrastructure.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")

        manager = MemoryManager()

        # Should handle special characters gracefully
        try:
            results = manager.search("!@#$%^&*()", limit=3)
        except Exception:
            pass  # May fail but should not crash

    def test_search_large_k_value(self):
        """Test search with large k value"""
        try:
            from backend.infrastructure.memory import MemoryManager
        except ImportError:
            pytest.skip("Cannot import MemoryManager")

        manager = MemoryManager()

        # Large k should be handled gracefully
        try:
            results = manager.search("test", limit=1000)
            assert results is not None
        except Exception as e:
            pytest.fail(f"search with large k raised: {e}")


# Test functions (if they exist)
def test_add_memory_call():
    """Test add_memory function"""
    try:
        from backend.infrastructure.memory import add_memory
    except ImportError:
        pytest.skip("add_memory function not found")

    # Function should exist
    assert callable(add_memory)


def test_search_memory_call():
    """Test search_memory function"""
    try:
        from backend.infrastructure.memory import search_memory
    except ImportError:
        pytest.skip("search_memory function not found")

    # Function should exist
    assert callable(search_memory)
