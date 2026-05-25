"""
⚠️ DEPRECATED — llm/router.py is removed.

All functionality moved to backend/infrastructure/legacy_llm_router.py.
Import directly from there. This shim will be deleted in a future version.
"""

import warnings

warnings.warn(
    "llm.router is deprecated. Use backend.infrastructure.legacy_llm_router instead.",
    DeprecationWarning,
    stacklevel=2,
)

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
