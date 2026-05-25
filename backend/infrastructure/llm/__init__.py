"""LLM Backend Package — dedicated clients per provider.

Structure:
  base.py       — LLMBackend abstract base class
  errors.py     — Custom exception hierarchy
  factory.py    — get_backend(provider) -> LLMBackend
  _openai_mixin.py — Shared OpenAI-compatible mixin
  ollama.py     — Ollama-specific client
  lmstudio.py   — LM Studio client (high-priority)
  lemonade.py   — Lemonade client (with /v1/completions fallback)
  llamacpp.py   — llama.cpp client
  health.py     — Health check utilities
"""

from backend.infrastructure.llm.base import LLMBackend
from backend.infrastructure.llm.errors import (
    LLMAuthenticationError,
    LLMBackendError,
    LLMConnectionError,
    LLMModelNotFoundError,
    LLMStreamError,
    LLMTimeoutError,
)
from backend.infrastructure.llm.factory import (
    get_backend,
    list_available_backends,
    register_backend,
)

__all__ = [
    "LLMAuthenticationError",
    "LLMBackend",
    "LLMBackendError",
    "LLMConnectionError",
    "LLMModelNotFoundError",
    "LLMStreamError",
    "LLMTimeoutError",
    "get_backend",
    "list_available_backends",
    "register_backend",
]
