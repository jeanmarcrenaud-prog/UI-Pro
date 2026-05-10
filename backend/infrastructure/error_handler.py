# services/error_handler.py - Centralized Error Handling & Recovery
"""
Role: Comprehensive error classification and recovery
Function: Classifies errors, provides user-friendly messages and recovery suggestions
"""

import logging
import traceback
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error classification categories."""
    LLM_GENERATION = "llm_generation"
    LLM_TIMEOUT = "llm_timeout"
    NETWORK = "network"
    MEMORY = "memory"
    EXECUTION = "execution"
    VALIDATION = "validation"
    PERMISSION = "permission"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


@dataclass
class ErrorDetails:
    """Structured error information with user-friendly messages."""
    category: ErrorCategory
    message: str
    user_message: str
    recovery_suggestion: str
    technical_details: Optional[str] = None
    stack_trace: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorMetrics:
    """Error tracking metrics"""
    total_errors: int = 0
    by_category: Dict[ErrorCategory, int] = field(default_factory=dict)
    last_error: Optional[ErrorDetails] = None
    recovery_success_rate: float = 1.0


class ErrorHandler:
    """
    Comprehensive error handling service with classification,
    user-friendly messages, and recovery suggestions.
    """

    ERROR_MESSAGES = {
        ErrorCategory.LLM_GENERATION: "The AI had trouble generating a response. Please try again with a simpler prompt.",
        ErrorCategory.LLM_TIMEOUT: "The AI is taking too long. Try a shorter or simpler request.",
        ErrorCategory.NETWORK: "Connection issue with the AI service. Check that Ollama (or your backend) is running.",
        ErrorCategory.MEMORY: "There was an issue accessing memory. Continuing without previous context.",
        ErrorCategory.EXECUTION: "The generated code encountered an error. The system will try to fix it.",
        ErrorCategory.VALIDATION: "Invalid input. Please check your request and try again.",
        ErrorCategory.RATE_LIMIT: "Too many requests. Please wait a moment before trying again.",
        ErrorCategory.UNKNOWN: "An unexpected error occurred. Please try again.",
    }

    RECOVERY_SUGGESTIONS = {
        ErrorCategory.LLM_TIMEOUT: "Try breaking your request into smaller parts or use a faster model.",
        ErrorCategory.NETWORK: "Run `ollama serve` in a terminal and try again.",
        ErrorCategory.LLM_GENERATION: "Simplify your prompt or switch to a different model (e.g., qwen3.6:latest).",
        ErrorCategory.EXECUTION: "The code will be reviewed and fixed automatically if possible.",
    }

    def __init__(self):
        self.metrics = ErrorMetrics()
        self._error_history: List[ErrorDetails] = []
        self._max_history = 50

    def classify_error(self, error: Exception, context: Optional[Dict] = None) -> ErrorCategory:
        """Classify exception into category."""
        error_str = str(error).lower()

        if any(kw in error_str for kw in ["timeout", "timed out", "took too long"]):
            return ErrorCategory.LLM_TIMEOUT

        if any(kw in error_str for kw in ["connection", "network", "refused", "unreachable"]):
            return ErrorCategory.NETWORK

        if any(kw in error_str for kw in ["ollama", "model", "generate", "llm"]):
            return ErrorCategory.LLM_GENERATION

        if any(kw in error_str for kw in ["memory", "faiss", "vector"]):
            return ErrorCategory.MEMORY

        if any(kw in error_str for kw in ["syntax", "indent", "nameerror", "attributeerror", "typeerror"]):
            return ErrorCategory.EXECUTION

        if any(kw in error_str for kw in ["permission", "forbidden", "access denied"]):
            return ErrorCategory.PERMISSION

        if any(kw in error_str for kw in ["rate", "quota", "too many requests"]):
            return ErrorCategory.RATE_LIMIT

        return ErrorCategory.UNKNOWN

    def handle(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> ErrorDetails:
        """Handle error and return user-friendly details."""
        category = self.classify_error(error, context)

        user_message = self.ERROR_MESSAGES.get(category, str(error))
        recovery = self.RECOVERY_SUGGESTIONS.get(category, "Please try again.")

        details = ErrorDetails(
            category=category,
            message=str(error),
            user_message=user_message,
            recovery_suggestion=recovery,
            technical_details=str(error)[:300],
            stack_trace=traceback.format_exc()[:800] if logger.isEnabledFor(logging.DEBUG) else None,
            context=context or {}
        )

        # Update metrics
        self.metrics.total_errors += 1
        self.metrics.by_category[category] = self.metrics.by_category.get(category, 0) + 1
        self.metrics.last_error = details

        # Store in history
        self._error_history.append(details)
        if len(self._error_history) > self._max_history:
            self._error_history = self._error_history[-self._max_history:]

        logger.error(f"[{category.value}] {error}")
        return details

    def should_retry(self, error: ErrorDetails) -> bool:
        """Determine if error is retryable"""
        retryable = [
            ErrorCategory.LLM_TIMEOUT,
            ErrorCategory.NETWORK,
            ErrorCategory.LLM_GENERATION,
            ErrorCategory.RATE_LIMIT,
        ]
        return error.category in retryable

    def get_retry_delay(self, attempt: int) -> int:
        """Get exponential backoff delay in seconds"""
        return min(2 ** attempt, 30)

    def get_metrics(self) -> Dict:
        """Get error metrics"""
        return {
            "total_errors": self.metrics.total_errors,
            "by_category": {k.value: v for k, v in self.metrics.by_category.items()},
            "last_error": {
                "category": self.metrics.last_error.category.value if self.metrics.last_error else None,
                "message": self.metrics.last_error.user_message if self.metrics.last_error else None,
                "timestamp": self.metrics.last_error.timestamp.isoformat() if self.metrics.last_error else None
            } if self.metrics.last_error else None
        }

    def get_recent_errors(self, limit: int = 10) -> List[ErrorDetails]:
        return self._error_history[-limit:]


# ====================== Singleton ======================

_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


__all__ = ["ErrorHandler", "ErrorDetails", "ErrorCategory", "ErrorMetrics", "get_error_handler"]