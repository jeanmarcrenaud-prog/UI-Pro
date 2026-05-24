"""
models/settings.py - Settings exports

Imports from the unified pydantic-settings based configuration.
"""

from backend.domain.settings import (
    DEFAULT_PRESETS,
    ModelPreset,
    Settings,
    get_settings,
    settings,
)

# Constants from settings instance (backward compatibility)
OLLAMA_URL = settings.ollama_url
LEMONADE_URL = settings.lemonade_url
LLAMACPP_URL = settings.llamacpp_url
LMSTUDIO_URL = settings.lmstudio_url

__all__ = [
    "DEFAULT_PRESETS",
    "LEMONADE_URL",
    "LLAMACPP_URL",
    "LMSTUDIO_URL",
    "OLLAMA_URL",
    "ModelPreset",
    "Settings",
    "get_settings",
    "settings",
]
