"""
models/settings.py - Settings exports

Imports from the unified pydantic-settings based configuration.
"""

from backend.domain.settings import (
    Settings,
    ModelPreset,
    DEFAULT_PRESETS,
    settings,
    get_settings,
)

# Constants from settings instance (backward compatibility)
OLLAMA_URL = settings.ollama_url
LEMONADE_URL = settings.lemonade_url
LLAMACPP_URL = settings.llamacpp_url
LMSTUDIO_URL = settings.lmstudio_url

__all__ = [
    "Settings",
    "ModelPreset",
    "DEFAULT_PRESETS",
    "settings",
    "get_settings",
    "OLLAMA_URL",
    "LEMONADE_URL",
    "LLAMACPP_URL",
    "LMSTUDIO_URL",
]