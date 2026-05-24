"""
llm/__init__.py - Legacy LLM Package

⚠️  This package has moved to backend/infrastructure/legacy_llm_router.py.
    This is a backward-compatibility shim.
"""

from backend.infrastructure.legacy_llm_router import LLMRouter, ModelConfig, OllamaClient
from models.settings import settings

# Convenience: get default client instance
_client = None


def get_client() -> OllamaClient:
    """Get default Ollama client instance"""
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def call(model: str, prompt: str) -> str:
    """Simple wrapper: call model with prompt"""
    client = get_client()
    return client.generate(prompt, model=model)


# Alias for settings
MODELS = {"fast": settings.model_fast, "reasoning": settings.model_reasoning}

__all__ = [
    "LLMRouter",
    "MODELS",
    "ModelConfig",
    "OllamaClient",
    "call",
    "get_client",
]
