# api/translations.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.transport.translations instead

from backend.transport.translations import (
    LANGUAGES,
    DEFAULT_LANGUAGE,
    TRANSLATIONS,
    LANGUAGE_OPTIONS,
    get_translation,
    get_current_translations,
)

__all__ = [
    "LANGUAGES",
    "DEFAULT_LANGUAGE",
    "TRANSLATIONS",
    "LANGUAGE_OPTIONS",
    "get_translation",
    "get_current_translations",
]