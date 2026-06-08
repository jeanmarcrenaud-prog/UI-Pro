"""
test_llm.py - Unit tests for LLM module (new backend system)

Tests for:
- get_backend factory
- ModelConfig usage
- Backend instantiation
- Model settings
"""

from backend.domain.settings import settings

from backend.infrastructure.llm.models import ModelConfig
from backend.infrastructure.llm.factory import get_backend, list_available_backends

# Convenience aliases
MODELS = {"fast": settings.model_fast, "reasoning": settings.model_reasoning}


def test_list_backends():
    """Test available backends are registered."""
    backends = list_available_backends()
    assert "ollama" in backends


class TestModelConfig:
    """Test ModelConfig dataclass."""

    def test_defaults(self):
        config = ModelConfig()
        assert config.backend == "ollama"

    def test_custom_config(self):
        config = ModelConfig(
            url="http://localhost:11434", model="qwen-opus", timeout=30
        )
        assert config.model == "qwen-opus"
        assert config.timeout == 30


class TestGetBackend:
    """Test get_backend factory."""

    def test_get_ollama(self):
        backend = get_backend("ollama")
        assert backend.backend_name == "ollama"

    def test_get_unknown_raises(self):
        from backend.infrastructure.llm.errors import LLMBackendError

        try:
            get_backend("nonexistent")
            assert False, "Should have raised"
        except LLMBackendError:
            pass


class TestModels:
    """Test MODELS configuration"""

    def test_models_defined(self):
        assert "fast" in MODELS
        assert "reasoning" in MODELS

    def test_models_are_strings(self):
        assert isinstance(MODELS["fast"], str)
        assert isinstance(MODELS["reasoning"], str)
