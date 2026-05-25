"""
⚠️ DEPRECATED — adapters package is removed.

All functionality moved to backend/infrastructure/adapters/.
Import directly from there. This shim will be deleted in a future version.
"""

import warnings

warnings.warn(
    "adapters is deprecated. Use backend.infrastructure.adapters instead.",
    DeprecationWarning,
    stacklevel=2,
)

from backend.infrastructure.adapters.faiss import FAISSAdapter  # noqa: F401

__all__ = [
    "FAISSAdapter",
]
