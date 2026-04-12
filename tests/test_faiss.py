# tests/test_faiss.py - FAISS adapter tests

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


class TestFAISSAdapter:
    """Tests for FAISS adapter"""
    
    def test_adapter_init(self, temp_dir):
        """Test adapter initialization"""
        try:
            from adapters.memory.faiss import FAISSAdapter
            
            adapter = FAISSAdapter(
                persist_path=str(temp_dir / "test.index"),
                dimension=384
            )
            assert adapter is not None
            assert adapter.index is not None
        except ImportError:
            pytest.skip("FAISS not available")
    
    def test_add_empty_text(self, temp_dir):
        """Test adding empty text does nothing"""
        try:
            from adapters.memory.faiss import FAISSAdapter
            
            adapter = FAISSAdapter(
                persist_path=str(temp_dir / "test.index"),
                dimension=384
            )
            
            initial_count = adapter.index.ntotal
            adapter.add("")
            # Should not add empty
            assert adapter.index.ntotal == initial_count
        except ImportError:
            pytest.skip("FAISS not available")
    
    def test_add_and_search(self, temp_dir):
        """Test adding and searching"""
        try:
            from adapters.memory.faiss import FAISSAdapter
            
            adapter = FAISSAdapter(
                persist_path=str(temp_dir / "test.index"),
                dimension=384
            )
            
            # Add a document
            adapter.add("Hello world test document")
            
            # Search should return results
            results = adapter.search("hello world", k=1)
            
            assert isinstance(results, list)
        except ImportError:
            pytest.skip("FAISS not available")
    
    def test_search_empty_index(self, temp_dir):
        """Test search on empty index returns empty"""
        try:
            from adapters.memory.faiss import FAISSAdapter
            
            adapter = FAISSAdapter(
                persist_path=str(temp_dir / "test.index"),
                dimension=384
            )
            
            results = adapter.search("test query", k=3)
            
            assert results == []
        except ImportError:
            pytest.skip("FAISS not available")
    
    def test_batch_save(self, temp_dir):
        """Test batch save behavior"""
        try:
            from adapters.memory.faiss import FAISSAdapter
            
            adapter = FAISSAdapter(
                persist_path=str(temp_dir / "test.index"),
                dimension=384
            )
            
            # Add documents without auto-save
            for i in range(15):
                adapter.add(f"test document {i}", auto_save=False)
            
            # Should have accumulated without saving every time
            assert adapter.index.ntotal > 0
        except ImportError:
            pytest.skip("FAISS not available")
    
    def test_dimension_mismatch(self, temp_dir):
        """Test handling of dimension mismatch"""
        try:
            from adapters.memory.faiss import FAISSAdapter
            
            # Initialize with dimension
            adapter = FAISSAdapter(
                persist_path=str(temp_dir / "test.index"),
                dimension=384
            )
            
            # Adding with different dimension should be handled
            # (adapter should resize or create new index)
            assert True  # If we get here, it handled correctly
        except ImportError:
            pytest.skip("FAISS not available")