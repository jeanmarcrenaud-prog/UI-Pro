"""
settings.py - UI-Pro Configuration

Backward compatibility wrapper - imports from models.settings.
"""

from models.settings import (
    settings,
    get_settings,
    Settings,
    ModelPreset,
    DEFAULT_PRESETS,
)

# Properties from settings instance
PROJECT_ROOT = settings.project_root
WORKSPACE = settings.workspace
TEMPLATES = settings.templates
OLLAMA_URL = settings.ollama_url
LEMONADE_URL = settings.lemonade_url
LLAMACPP_URL = settings.llamacpp_url
LMSTUDIO_URL = settings.lmstudio_url
MODEL_FAST = settings.model_fast
MODEL_REASONING = settings.model_reasoning
MODEL_CODE = settings.model_code
LLM_TIMEOUT = settings.llm_timeout
EXECUTOR_TIMEOUT = settings.executor_timeout
LOG_LEVEL = settings.log_level


def get_model_for_task(task: str) -> str:
    """Wrapper for Settings.get_model_for_task() method."""
    return settings.get_model_for_task(task)


__all__ = [
    "settings",
    "get_settings",
    "get_model_for_task",
    "Settings",
    "ModelPreset",
    "DEFAULT_PRESETS",
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
]