"""
models/settings.py - Backward Compatibility Re-export

Imports from both v1 (legacy) and v2 (pydantic-settings) for compatibility.
New code should use v2 (settings_v2).
"""

# V2 - New pydantic-settings based configuration
from backend.domain.settings_v2 import (
    Settings as SettingsV2,
    ModelPreset,
    DEFAULT_PRESETS,
    get_settings as get_settings_v2,
)

# V1 - Legacy (for backward compatibility during migration)
from backend.domain.settings import (
    Settings as SettingsV1,
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
    settings as settings_v1,
    get_settings as get_settings_v1,
)

# Aliases for easy migration
Settings = SettingsV2
settings = get_settings_v2()
get_settings = get_settings_v2

__all__ = [
    # V2 (preferred)
    "Settings",
    "SettingsV2",
    "ModelPreset",
    "DEFAULT_PRESETS",
    "settings",
    "get_settings",
    # V1 (legacy)
    "SettingsV1",
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
    "settings_v1",
    "get_settings_v1",
]