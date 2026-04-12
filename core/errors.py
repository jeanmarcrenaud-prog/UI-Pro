# core/errors.py - Hiérarchie d'exceptions métier pour UI-Pro

from typing import Optional


class DomainError(Exception):
    """Erreur métier de base pour UI-Pro"""
    
    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class LLMError(DomainError):
    """Erreur lors d'un appel LLM"""
    
    def __init__(self, message: str, model: Optional[str] = None, backend: Optional[str] = None):
        self.model = model
        self.backend = backend
        super().__init__(message, code="LLM_ERROR")
    
    def __str__(self):
        base = super().__str__()
        parts = []
        if self.model:
            parts.append(f"model: {self.model}")
        if self.backend:
            parts.append(f"backend: {self.backend}")
        if parts:
            return f"{base} ({', '.join(parts)})"
        return base


class LLMBackendError(LLMError):
    """Erreur de backend (connexion, timeout, etc.)"""
    
    def __init__(self, message: str, backend: str, model: Optional[str] = None):
        super().__init__(message, model=model)
        self.code = "LLM_BACKEND_ERROR"
    
    def __str__(self):
        return f"Backend error: {self.message} (backend: {self.backend})"


class LLMTimeoutError(LLMError):
    """Timeout lors de l'appel LLM"""
    
    def __init__(self, message: str, model: str, timeout: int):
        super().__init__(message, model=model)
        self.code = "LLM_TIMEOUT"
        self.timeout = timeout
    
    def __str__(self):
        return f"Timeout after {self.timeout}s: {self.message}"


class ToolExecutionError(DomainError):
    """Erreur lors de l'exécution d'un outil"""
    
    def __init__(self, message: str, tool_name: Optional[str] = None):
        self.tool_name = tool_name
        super().__init__(message, code="TOOL_ERROR")
    
    def __str__(self):
        base = super().__str__()
        if self.tool_name:
            return f"{base} (tool: {self.tool_name})"
        return base


class MemoryError(DomainError):
    """Erreur mémoire/FAISS"""
    
    def __init__(self, message: str):
        super().__init__(message, code="MEMORY_ERROR")


class TimeoutError(DomainError):
    """Erreur de timeout"""
    
    def __init__(self, message: str, timeout_seconds: Optional[int] = None):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, code="TIMEOUT_ERROR")
    
    def __str__(self):
        base = super().__str__()
        if self.timeout_seconds:
            return f"{base} (timeout: {self.timeout_seconds}s)"
        return base


class SandboxError(DomainError):
    """Erreur sandbox/exécution"""
    
    def __init__(self, message: str):
        super().__init__(message, code="SANDBOX_ERROR")


class ValidationError(DomainError):
    """Erreur de validation d'entrée"""
    
    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(message, code="INVALID_INPUT")
    
    def __str__(self):
        base = super().__str__()
        if self.field:
            return f"{base} (field: {self.field})"
        return base


# Mapping vers codes HTTP
ERROR_TO_STATUS = {
    "INVALID_INPUT": 400,
    "LLM_ERROR": 500,
    "TOOL_ERROR": 500,
    "MEMORY_ERROR": 500,
    "TIMEOUT_ERROR": 504,
    "SANDBOX_ERROR": 500,
    "DOMAIN_ERROR": 500,
}


def error_to_http_status(code: str) -> int:
    """Retourne le code HTTP对应的"""
    return ERROR_TO_STATUS.get(code, 500)