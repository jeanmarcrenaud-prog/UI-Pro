"""Custom exception hierarchy for LLM backend clients."""


class LLMBackendError(Exception):
    """Base exception for all LLM backend errors."""


class LLMConnectionError(LLMBackendError):
    """Connection refused or unreachable backend."""


class LLMAuthenticationError(LLMBackendError):
    """401 or 403 response from backend."""


class LLMModelNotFoundError(LLMBackendError):
    """Model not found on backend (404)."""


class LLMTimeoutError(LLMBackendError):
    """Backend-specific timeout exceeded."""


class LLMStreamError(LLMBackendError):
    """Streaming failure during token generation."""


__all__ = [
    "LLMAuthenticationError",
    "LLMBackendError",
    "LLMConnectionError",
    "LLMModelNotFoundError",
    "LLMStreamError",
    "LLMTimeoutError",
]
