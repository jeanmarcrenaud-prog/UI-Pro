"""
Centralized logging system for UI-Pro.
Provides structured logging with rotation, multiple levels, and JSON formatting.
"""

import logging
import os
from typing import Optional
from logging.handlers import RotatingFileHandler
from pathlib import Path
import datetime
import json


# Log file configuration
LOGS_DIR = Path("logs")
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB per file
BACKUP_COUNT = 3  # Keep fewer backup files
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
    """Format logs as JSON for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
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
    """Centralized logger manager - singleton pattern."""
    
    _instance: Optional["LoggerManager"] = None
    _loggers: dict = {}
    _initialization_done = False
    
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
    
    # Test exception logging
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error("Division by zero occurred", exc_info=True)
