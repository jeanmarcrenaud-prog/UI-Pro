"""
models/settings.py - Backward Compatibility Re-export
"""
from backend.domain.settings import (
    Settings,
    PROJECT_ROOT,
    WORKSPACE,
    TEMPLATES,
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
    "PROJECT_ROOT",
    "WORKSPACE",
    "TEMPLATES",
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