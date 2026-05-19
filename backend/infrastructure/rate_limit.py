"""
Rate limiting and API authentication middleware.
"""

import time
import hashlib
import logging
from typing import Optional, Dict
from dataclasses import dataclass
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._buckets: Dict[str, Dict] = {}
    
    def _get_client_id(self, request: Request) -> str:
        """Get unique client identifier."""
        # Use API key if present, otherwise use IP
        api_key = request.headers.get("x-api-key")
        if api_key:
            return f"api:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
        
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        
        return f"ip:{ip}"
    
    def _get_bucket(self, client_id: str) -> Dict:
        """Get or create bucket for client."""
        now = time.time()
        
        if client_id not in self._buckets:
            self._buckets[client_id] = {
                "tokens": self.config.burst_size,
                "last_update": now,
                "minute_count": 0,
                "minute_start": now,
                "hour_count": 0,
                "hour_start": now,
            }
        
        bucket = self._buckets[client_id]
        
        # Reset minute counter
        if now - bucket["minute_start"] > 60:
            bucket["minute_count"] = 0
            bucket["minute_start"] = now
        
        # Reset hour counter
        if now - bucket["hour_start"] > 3600:
            bucket["hour_count"] = 0
            bucket["hour_start"] = now
        
        # Refill tokens (1 per second)
        elapsed = now - bucket["last_update"]
        bucket["tokens"] = min(
            self.config.burst_size,
            bucket["tokens"] + elapsed
        )
        bucket["last_update"] = now
        
        return bucket
    
    def check(self, request: Request) -> bool:
        """Check if request is allowed. Returns True if allowed."""
        client_id = self._get_client_id(request)
        bucket = self._get_bucket(client_id)
        now = time.time()
        
        # Check minute limit
        if bucket["minute_count"] >= self.config.requests_per_minute:
            logger.warning(f"Rate limit exceeded (minute): {client_id}")
            return False
        
        # Check hour limit
        if bucket["hour_count"] >= self.config.requests_per_hour:
            logger.warning(f"Rate limit exceeded (hour): {client_id}")
            return False
        
        # Check tokens
        if bucket["tokens"] < 1:
            logger.warning(f"Rate limit exceeded (burst): {client_id}")
            return False
        
        # Consume resources
        bucket["tokens"] -= 1
        bucket["minute_count"] += 1
        bucket["hour_count"] += 1
        
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting."""
    
    def __init__(self, app, config: RateLimitConfig = None):
        super().__init__(app)
        self.limiter = RateLimiter(config)
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/docs", "/openapi.json", "/ws"]:
            return await call_next(request)
        
        if not self.limiter.check(request):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = "60"
        response.headers["X-RateLimit-Remaining"] = "59"
        
        return response


# API Key authentication
class APIKeyAuth:
    """Simple API key authentication."""
    
    def __init__(self):
        self._keys: Dict[str, Dict] = {}  # key -> {name, rate_limit, created}
    
    def add_key(self, key: str, name: str = "default", rate_limit: int = 60):
        """Add an API key."""
        self._keys[key] = {
            "name": name,
            "rate_limit": rate_limit,
            "created": time.time()
        }
    
    def verify(self, key: Optional[str]) -> bool:
        """Verify an API key."""
        if not key:
            return False
        return key in self._keys
    
    def get_rate_limit(self, key: str) -> int:
        """Get rate limit for key."""
        if key in self._keys:
            return self._keys[key]["rate_limit"]
        return 60


# Singleton instances
_rate_limiter: Optional[RateLimiter] = None
_api_auth: Optional[APIKeyAuth] = None


def get_rate_limiter() -> RateLimiter:
    """Get singleton rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_api_auth() -> APIKeyAuth:
    """Get singleton API auth."""
    global _api_auth
    if _api_auth is None:
        _api_auth = APIKeyAuth()
    return _api_auth


__all__ = [
    "RateLimitConfig",
    "RateLimiter", 
    "RateLimitMiddleware",
    "APIKeyAuth",
    "get_rate_limiter",
    "get_api_auth",
]