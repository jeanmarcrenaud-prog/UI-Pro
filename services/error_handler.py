# services/error_handler.py - Error Handling Service
#
# Role: Comprehensive error classification and recovery
# Function: Classifies errors, provides user-friendly messages and recovery suggestions
#
# Features:
# - Error classification
# - User-friendly messages
# - Recovery suggestions
# - Logging and metrics

import logging
import traceback
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error category classification"""
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
    """Structured error information"""
    category: ErrorCategory
    message: str
    user_message: str  # User-friendly message
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
    Service for handling errors with user-friendly feedback.
    
    Features:
    - Error classification
    - User-friendly messages
    - Recovery suggestions
    - Error metrics
    - Retry logic
    """
    
    # User-friendly message templates
    ERROR_MESSAGES = {
        ErrorCategory.LLM_GENERATION: {
            "default": "The AI had trouble generating a response. Please try again.",
            "retry": "The AI response was incomplete. Retrying..."
        },
        ErrorCategory.LLM_TIMEOUT: {
            "default": "The AI is taking too long to respond. Please try a simpler request.",
            "timeout": "The request took too long. Try breaking it into smaller steps."
        },
        ErrorCategory.NETWORK: {
            "default": "Unable to connect to the AI service. Check your connection.",
            "retry": "Connection lost. Retrying..."
        },
        ErrorCategory.MEMORY: {
            "default": "There was an issue accessing memory. The conversation may be affected.",
            "retry": "Memory search failed. Continuing without context..."
        },
        ErrorCategory.EXECUTION: {
            "default": "There was an error running the generated code.",
            "syntax": "The code has a syntax error. Please try a different approach.",
            "timeout": "The code took too long to run.",
            "permission": "The code tried to do something not allowed."
        },
        ErrorCategory.VALIDATION: {
            "default": "The input provided was invalid. Please check and try again.",
            "empty": "No input was provided. Please enter something.",
            "too_long": "The input is too long. Please shorten it."
        },
        ErrorCategory.RATE_LIMIT: {
            "default": "Too many requests. Please wait a moment and try again."
        }
    }
    
    def __init__(self):
        self.metrics = ErrorMetrics()
        self._error_history: List[ErrorDetails] = []
        self._max_history = 100
    
    def classify_error(self, error: Exception, context: Dict = None) -> ErrorCategory:
        """Classify error into category"""
        error_str = str(error).lower()
        
        # Check error message patterns
        if any(x in error_str for x in ["timeout", "timed out"]):
            return ErrorCategory.LLM_TIMEOUT
        
        if any(x in error_str for x in ["connection", "network", "socket", "refused"]):
            return ErrorCategory.NETWORK
        
        if any(x in error_str for x in ["ollama", "llm", "model", "generate"]):
            return ErrorCategory.LLM_GENERATION
        
        if any(x in error_str for x in ["memory", "faiss", "vector"]):
            return ErrorCategory.MEMORY
        
        if any(x in error_str for x in ["syntax", "indentation", "nameerror", "attributeerror"]):
            return ErrorCategory.EXECUTION
        
        if any(x in error_str for x in ["permission", "access", "forbidden"]):
            return ErrorCategory.PERMISSION
        
        if any(x in error_str for x in ["rate", "too many", "quota"]):
            return ErrorCategory.RATE_LIMIT
        
        return ErrorCategory.UNKNOWN
    
    def handle(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
        user_context: str = None
    ) -> ErrorDetails:
        """
        Handle error and create user-friendly error details.
        
        Args:
            error: The exception that occurred
            context: Additional context (prompt, mode, etc.)
            user_context: User's original input
            
        Returns:
            ErrorDetails: Structured error information
        """
        category = self.classify_error(error, context)
        
        # Get user-friendly message
        messages = self.ERROR_MESSAGES.get(category, {})
        user_message = messages.get("default", str(error))
        
        # Get recovery suggestion
        suggestion = self._get_suggestion(category, error, context)
        
        # Create error details
        details = ErrorDetails(
            category=category,
            message=str(error),
            user_message=user_message,
            recovery_suggestion=suggestion,
            technical_details=str(error)[:200],
            stack_trace=traceback.format_exc()[:500] if logger.isEnabledFor(logging.DEBUG) else None,
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
        
        logger.error(f"Error handled: {category.value} - {error}")
        
        return details
    
    def _get_suggestion(self, category: ErrorCategory, error: Exception, context: Dict = None) -> str:
        """Get recovery suggestion based on error category"""
        suggestions = {
            ErrorCategory.LLM_TIMEOUT: "Try a shorter or simpler prompt. The AI is taking too long.",
            ErrorCategory.NETWORK: "Check that Ollama is running: 'ollama serve'. Try again in a moment.",
            ErrorCategory.LLM_GENERATION: "The model may be overloaded. Try again or use a different mode.",
            ErrorCategory.MEMORY: "Memory search failed. Continuing without previous context.",
            ErrorCategory.EXECUTION: "The generated code had an error. The system will try to fix it automatically.",
            ErrorCategory.VALIDATION: "Please check your input and try again with valid data.",
            ErrorCategory.RATE_LIMIT: "Please wait a few seconds before trying again.",
            ErrorCategory.UNKNOWN: "An unexpected error occurred. Please try again."
        }
        
        return suggestions.get(category, "Please try again.")
    
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
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """Get recent errors"""
        recent = self._error_history[-limit:]
        return [
            {
                "category": e.category.value,
                "message": e.user_message,
                "timestamp": e.timestamp.isoformat(),
                "recovery": e.recovery_suggestion
            }
            for e in recent
        ]


# Singleton
_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get singleton error handler"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


__all__ = [
    "ErrorHandler",
    "ErrorDetails",
    "ErrorCategory",
    "ErrorMetrics",
    "get_error_handler"
]