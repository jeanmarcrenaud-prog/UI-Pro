"""
settings.py - UI-Pro Configuration

Backward compatibility wrapper - imports from models.settings.
"""

from models.settings import (
    DEFAULT_PRESETS,
    ModelPreset,
    Settings,
    get_settings,
    settings,
)

# Properties from settings instance
PROJECT_ROOT = settings.project_root
WORKSPACE = str(settings.workspace_path)
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
    "DEFAULT_PRESETS",
    "EXECUTOR_TIMEOUT",
    "LEMONADE_URL",
    "LLAMACPP_URL",
    "LLM_TIMEOUT",
    "LMSTUDIO_URL",
    "LOG_LEVEL",
    "MODEL_CODE",
    "MODEL_FAST",
    "MODEL_REASONING",
    "OLLAMA_URL",
    "PROJECT_ROOT",
    "TEMPLATES",
    "WORKSPACE",
    "ModelPreset",
    "Settings",
    "get_model_for_task",
    "get_settings",
    "settings",
]
