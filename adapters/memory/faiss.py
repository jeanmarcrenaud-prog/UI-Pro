"""
⚠️ DEPRECATED — adapters/memory/faiss.py is removed.

All functionality moved to backend/infrastructure/adapters/faiss.py.
Import directly from there. This shim will be deleted in a future version.
"""

import warnings

warnings.warn(
    "adapters.memory.faiss is deprecated. Use backend.infrastructure.adapters.faiss instead.",
    DeprecationWarning,
    stacklevel=2,
)

from backend.infrastructure.adapters.faiss import FAISSAdapter  # noqa: F401

__all__ = ["FAISSAdapter"]
