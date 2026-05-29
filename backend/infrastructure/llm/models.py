"""Shared data models for LLM backends.

Extracted from legacy_llm_router.py to break circular dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelConfig:
    """LLM Backend Configuration."""

    url: str = ""
    model: str = ""
    timeout: int = 120
    backend: str = "ollama"


__all__ = ["ModelConfig"]
