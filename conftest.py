"""
conftest.py - Pytest configuration and shared fixtures
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import tempfile
import shutil

# Import project modules for testing
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import only what conftest needs
from llm import call, smart_call, OLLAMA_URL
from core.memory import MemoryManager, add_memory, search_memory

# =========================================
# FIXTURES
# =========================================

@pytest.fixture
def mock_ollama_response():
    """Fixture providing a mocked Ollama API response"""
    return {
        "response": "Mocked response from Ollama",
        "model": "qwen-opus"
    }

@pytest.fixture
def mock_subprocess_run():
    """Fixture for mocking subprocess.run"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Success output",
            stderr=""
        )
        yield mock_run

@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace directory for testing"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace.create("test.py", content="print('test')")
    
    with patch.dict(os.environ, {"WORKSPACE": str(workspace)}):
        yield workspace
    shutil.rmtree(workspace, ignore_errors=True)

@pytest.fixture
def mock_web_search_result():
    """Mock web search results"""
    return [
        {"title": "Python Documentation", "link": "https://docs.python.org/3/"},
        {"title": "Python Tutorial", "link": "https://tutorial.python.org/"},
    ]

@pytest.fixture
def mock_faiss_index():
    """Create a mock FAISS index for testing"""
    try:
        import faiss
        import numpy as np
        
        # Create a small FAISS index
        dimension = 384
        index = faiss.IndexFlatL2(dimension)
        dummy_vectors = np.random.rand(10, dimension).astype('float32')
        index.add(dummy_vectors)
        
        return index, dimension
    except ImportError:
        # Fallback if FAISS not installed
        return None, None

@pytest.fixture
def config_override(monkeypatch):
    """Fixture to override config values for testing"""
    monkeypatch.setenv("HF_TOKEN", "test_token")
    monkeypatch.setenv("MODEL_FAST", "qwen2.5-coder:32b")
    monkeypatch.setenv("MODEL_REASONING", "qwen-opus")
    monkeypatch.setenv("LLM_TIMEOUT", "10")
    monkeypatch.setenv("EXECUTOR_TIMEOUT", "30")
    yield
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("MODEL_FAST", raising=False)
    monkeypatch.delenv("MODEL_REASONING", raising=False)

# =========================================
# AUTOMATIQUE FIXTURES
# =========================================

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Log test start for debugging"""
    if "LOG_LEVEL" in os.environ:
        marker = item.get_closest_marker("unit")
        if marker and os.environ.get("LOG_LEVEL") == "DEBUG":
            item.log_start = True
            item.log_debug = True

