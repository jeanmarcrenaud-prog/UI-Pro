"""
llm/router.py - Legacy LLM Router

⚠️  This module has moved to backend/infrastructure/legacy_llm_router.py.
    This is a backward-compatibility shim. New code should import directly
    from backend.infrastructure.legacy_llm_router.
"""

from backend.infrastructure.legacy_llm_router import (
    LLMRouter,
    ModelConfig,
    ModelsConfig,
    OllamaClient,
    get_llm_router,
)

__all__ = [
    "LLMRouter",
    "ModelConfig",
    "ModelsConfig",
    "OllamaClient",
    "get_llm_router",
]
