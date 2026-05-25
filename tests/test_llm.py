"""
test_llm.py - Unit tests for LLM module

Tests for:
- OllamaClient instantiation
- Model configuration
- MODELS settings
"""

from backend.infrastructure.legacy_llm_router import ModelConfig, OllamaClient
from models.settings import settings

# Replicate legacy convenience aliases (previously from llm/ shim)
MODELS = {"fast": settings.model_fast, "reasoning": settings.model_reasoning}
_client = None


def get_client() -> OllamaClient:
    """Get default OllamaClient singleton."""
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def call(model: str, prompt: str) -> str:
    """Call model with prompt."""
    return get_client().generate(prompt, model=model)


class TestOllamaClient:
    """Test OllamaClient class"""

    def test_client_instantiation(self):
        """Test client can be instantiated"""
        client = OllamaClient()
        assert client is not None

    def test_client_with_config(self):
        """Test client with custom config"""
        config = ModelConfig(
            url="http://localhost:11434", model="qwen-opus", timeout=30
        )
        client = OllamaClient(config)
        assert client.config.model == "qwen-opus"


class TestCall:
    """Test call() wrapper function"""

    def test_call_is_function(self):
        """Test call() is a function"""
        assert callable(call)

    def test_call_accepts_params(self):
        """Test call() accepts model and prompt"""
        # Just verify the function signature - don't call with no Ollama running
        import inspect

        sig = inspect.signature(call)
        assert "model" in sig.parameters
        assert "prompt" in sig.parameters


class TestGetClient:
    """Test get_client() singleton"""

    def test_get_client_returns_client(self):
        """Test get_client returns OllamaClient"""
        client = get_client()
        assert isinstance(client, OllamaClient)


class TestModels:
    """Test MODELS configuration"""

    def test_models_defined(self):
        """Test MODELS has fast and reasoning keys"""
        assert "fast" in MODELS
        assert "reasoning" in MODELS

    def test_models_are_strings(self):
        """Test model names are strings"""
        assert isinstance(MODELS["fast"], str)
        assert isinstance(MODELS["reasoning"], str)
