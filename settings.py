"""
settings.py - UI-Pro Configuration

Backward compatibility wrapper - imports from models.settings.
"""

from models.settings import (
    settings,
    get_settings,
    get_model_for_task,
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
    LLM_TIMEOUT,
    EXECUTOR_TIMEOUT,
    LOG_LEVEL,
    BACKENDS,
)

__all__ = [
    "settings",
    "get_settings",
    "get_model_for_task",
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
    "LLM_TIMEOUT",
    "EXECUTOR_TIMEOUT",
    "LOG_LEVEL",
    "BACKENDS",
]