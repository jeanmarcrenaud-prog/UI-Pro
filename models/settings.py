"""
models/settings.py - Backward Compatibility Re-export
"""
from backend.domain.settings import (
    Settings,
    OLLAMA_URL,
    LEMONADE_URL,
    LLAMACPP_URL,
    LMSTUDIO_URL,
    MODEL_FAST,
    MODEL_REASONING,
    MODEL_CODE,
    LLM_TIMEOUT,
    EXECUTOR_TIMEOUT,
    LOG_LEVEL,
    REASONING_KEYWORDS,
    settings,
    get_settings,
)

__all__ = [
    "Settings",
    "OLLAMA_URL",
    "LEMONADE_URL",
    "LLAMACPP_URL",
    "LMSTUDIO_URL",
    "MODEL_FAST",
    "MODEL_REASONING",
    "MODEL_CODE",
    "LLM_TIMEOUT",
    "EXECUTOR_TIMEOUT",
    "LOG_LEVEL",
    "REASONING_KEYWORDS",
    "settings",
    "get_settings",
]