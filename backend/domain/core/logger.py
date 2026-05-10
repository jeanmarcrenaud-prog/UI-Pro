"""
Enhanced logging system for UI-Pro.
Provides structured logging with rotation, multiple levels, JSON formatting,
correlation IDs, and performance metrics.
"""

import logging
import os
import threading
import time
import uuid
from typing import Optional
from logging.handlers import RotatingFileHandler
from pathlib import Path
import datetime
import json
from contextvars import ContextVar


# Context variable for correlation ID
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


# Log file configuration
LOGS_DIR = Path("logs")
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB per file
BACKUP_COUNT = 5  # Keep more backup files for better history
LOG_ROTATE_THRESHOLD = 1 * 1024 * 1024  # Only backup if > 1MB

# Log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging with correlation IDs and metrics."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Get correlation ID from context
        correlation_id = correlation_id_ctx.get()
        
        log_data = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add correlation ID if present
        if correlation_id:
            log_data["correlation_id"] = correlation_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            # Use exc_text if available (handles some edge cases)
            log_data["exception"] = record.exc_text
         
        # Collect extra fields (non-standard attributes)
        extra_keys = (
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process",
        )
        extras = {k: v for k, v in record.__dict__.items() if k not in extra_keys}
        if extras:
            log_data["extra"] = extras
         
        return json.dumps(log_data)


class LoggerManager:
    """Enhanced centralized logger manager - singleton pattern with performance tracking."""
    
    _instance: Optional["LoggerManager"] = None
    _loggers: dict = {}
    _initialization_done = False
    _start_time = time.time()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._initialization_done = False
        return cls._instance
    
    def __init__(self):
        if self._initialization_done:
            return
        self._initialization_done = True
        self._setup_logging()
    
    def _setup_logging(self):
        """Initialize log directory and root logger."""
        # Create logs directory
        LOGS_DIR.mkdir(exist_ok=True)
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Check if handlers already exist to avoid duplicates
        if root_logger.handlers:
            return
        
        # Console handler with color-coded output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(levelname)s - %(name)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler with rotation and JSON formatting
        log_file = LOGS_DIR / "app.log"
        
        # Only backup if file is large (>1MB threshold)
        if log_file.exists() and log_file.stat().st_size > LOG_ROTATE_THRESHOLD:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = log_file.with_name(f"app_{timestamp}.log")
            try:
                os.rename(str(log_file), str(backup_name))
            except OSError:
                pass  # Keep original if rename fails
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
        
        # Log startup using the root logger directly
        root_logger.info("Logging system initialized")
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger with given name (singleton per name)."""
        if name not in self._loggers:
            logger = logging.getLogger(name)
            
            # Set log level if environment variable specified
            env_level = os.environ.get("LOG_LEVEL", "INFO")
            level = LOG_LEVELS.get(env_level.upper(), logging.INFO)
            logger.setLevel(level)
            
            self._loggers[name] = logger
        
        return self._loggers[name]
    
    def set_level(self, name: str, level: int):
        """Set log level for specific logger."""
        if name in self._loggers:
            self._loggers[name].setLevel(level)
    
    def get_uptime(self) -> float:
        """Get logger uptime in seconds."""
        return time.time() - self._start_time


def set_correlation_id(correlation_id: str):
    """Set the correlation ID for the current context."""
    correlation_id_ctx.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return correlation_id_ctx.get()


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


# Global logger instance
_logger_manager = LoggerManager()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
        
    Example:
        >>> from logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting application")
    """
    return _logger_manager.get_logger(name)


def debug(msg: str, module: str = __name__, func: str = "", line: int = 0):
    """Convenience function for debug logs."""
    logger = get_logger(module)
    if func and line > 0:
        logger.debug(f"[{func}:{line}] {msg}")
    else:
        logger.debug(msg)


def info(msg: str, module: str = __name__, func: str = "", line: int = 0):
    """Convenience function for info logs."""
    logger = get_logger(module)
    if func and line > 0:
        logger.info(f"[{func}:{line}] {msg}")
    else:
        logger.info(msg)


def warning(msg: str, module: str = __name__, func: str = "", line: int = 0):
    """Convenience function for warning logs."""
    logger = get_logger(module)
    if func and line > 0:
        logger.warning(f"[{func}:{line}] {msg}")
    else:
        logger.warning(msg)


def error(msg: str, module: str = __name__, exc_info: bool = False):
    """Convenience function for error logs."""
    logger = get_logger(module)
    logger.error(msg, exc_info=exc_info)


def critical(msg: str, module: str = __name__, exc_info: bool = False):
    """Convenience function for critical logs."""
    logger = get_logger(module)
    logger.critical(msg, exc_info=exc_info)


def log_performance(operation: str, duration_ms: float, module: str = __name__, **kwargs):
    """Log performance metrics."""
    logger = get_logger(module)
    extra_data = {
        "operation": operation,
        "duration_ms": duration_ms,
        **kwargs
    }
    logger.info(f"PERFORMANCE: {operation} took {duration_ms:.2f}ms", extra=extra_data)


# Example usage
if __name__ == "__main__":
    # Setup test logging
    import logging as stdlib_logging
    stdlib_logging.basicConfig(level=stdlib_logging.DEBUG, format="%(levelname)s - %(message)s")
    
    logger = get_logger(__name__)
    logger.info("Logger initialized successfully")
    logger.debug("This is a debug message")
    logger.warning("This is a warning message")
    logger.error("This is an error message", exc_info=False)
    
    # Test correlation ID
    corr_id = generate_correlation_id()
    set_correlation_id(corr_id)
    logger.info(f"Test message with correlation ID: {corr_id}")
    
    # Test performance logging
    log_performance("test_operation", 42.5, module=__name__, item_count=100)
    
    # Test exception logging
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error("Division by zero occurred", exc_info=True)
