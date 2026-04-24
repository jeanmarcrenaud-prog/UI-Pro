# services/base.py - Base Service Interface
#
# Role: Abstract base class for all services with common functionality
# Function: Provides standardized logging, health checks, and metrics tracking
#
# Features:
# - Logging structuré
# - Health check interface
# - Metrics de base

import logging
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime


class BaseService(ABC):
    """
    Base class for all services.
    
    Provides:
    - Standardized logging
    - Health check interface
    - Metrics tracking
    """
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"services.{self.name}")
        self._initialized_at = datetime.now()
        self._health_status = "healthy"
        self._last_error: Optional[str] = None
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service"""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Clean shutdown"""
        pass
    
    def health_check(self) -> dict:
        """
        Return service health status.
        
        Returns:
            dict: Health status with status, initialized_at, error
        """
        return {
            "service": self.name,
            "status": self._health_status,
            "initialized_at": self._initialized_at.isoformat(),
            "error": self._last_error
        }
    
    def _set_error(self, error: str) -> None:
        """Track last error"""
        self._last_error = error
        self._health_status = "unhealthy"
        self.logger.error(f"Service error: {error}")
    
    def _clear_error(self) -> None:
        """Clear error state"""
        self._last_error = None
        self._health_status = "healthy"


class ServiceMetrics:
    """Basic metrics for services"""
    
    def __init__(self):
        self.total_calls = 0
        self.failed_calls = 0
        self.total_latency_ms = 0.0
    
    def record_call(self, latency_ms: float, success: bool = True) -> None:
        """Record a service call"""
        self.total_calls += 1
        self.total_latency_ms += latency_ms
        if not success:
            self.failed_calls += 1
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return (self.total_calls - self.failed_calls) / self.total_calls
    
    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls
    
    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 2)
        }