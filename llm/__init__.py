# llm/__init__.py - LLM Package Entry Point
#
# Role: Public API for LLM agents
# Exports: OllamaClient, ModelConfig, LLMRouter from router
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.router import LLMRouter, ModelConfig, OllamaClient
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
