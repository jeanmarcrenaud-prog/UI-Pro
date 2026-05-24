"""
adapters/memory/faiss.py - FAISS Vector Store (Legacy re-export)

NOTE: This module re-exports FAISSAdapter from the canonical location at
backend/infrastructure/adapters/faiss.py to maintain backward compatibility.
New code should import directly from backend.infrastructure.adapters.faiss.
"""

from backend.infrastructure.adapters.faiss import FAISSAdapter  # noqa: F401

__all__ = ["FAISSAdapter"]
