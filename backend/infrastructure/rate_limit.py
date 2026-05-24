"""
Rate limiting and API authentication middleware.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field

from typing import Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool = True
    remaining_minute: int = 60
    remaining_hour: int = 1000
    remaining_burst: int = 10


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._buckets: dict[str, dict] = {}

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

    def _get_bucket(self, client_id: str) -> dict:
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
        bucket["tokens"] = min(self.config.burst_size, bucket["tokens"] + elapsed)
        bucket["last_update"] = now

        return bucket

    def check(self, request: Request) -> RateLimitResult:
        """Check if request is allowed. Returns RateLimitResult with remaining counts."""
        client_id = self._get_client_id(request)
        bucket = self._get_bucket(client_id)

        remaining_min = self.config.requests_per_minute - bucket["minute_count"]
        remaining_hr = self.config.requests_per_hour - bucket["hour_count"]
        remaining_burst = max(0, int(bucket["tokens"]))

        # Check minute limit
        if bucket["minute_count"] >= self.config.requests_per_minute:
            logger.warning(f"Rate limit exceeded (minute): {client_id}")
            return RateLimitResult(
                allowed=False,
                remaining_minute=0,
                remaining_hour=remaining_hr,
                remaining_burst=remaining_burst,
            )

        # Check hour limit
        if bucket["hour_count"] >= self.config.requests_per_hour:
            logger.warning(f"Rate limit exceeded (hour): {client_id}")
            return RateLimitResult(
                allowed=False,
                remaining_minute=remaining_min,
                remaining_hour=0,
                remaining_burst=remaining_burst,
            )

        # Check tokens
        if bucket["tokens"] < 1:
            logger.warning(f"Rate limit exceeded (burst): {client_id}")
            return RateLimitResult(
                allowed=False,
                remaining_minute=remaining_min,
                remaining_hour=remaining_hr,
                remaining_burst=0,
            )

        # Consume resources
        bucket["tokens"] -= 1
        bucket["minute_count"] += 1
        bucket["hour_count"] += 1

        return RateLimitResult(
            allowed=True,
            remaining_minute=remaining_min - 1 if remaining_min > 0 else 0,
            remaining_hour=remaining_hr - 1 if remaining_hr > 0 else 0,
            remaining_burst=max(0, int(bucket["tokens"])),
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting."""

    def __init__(self, app, config: Optional[RateLimitConfig] = None):
        super().__init__(app)
        self.limiter = RateLimiter(config)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/docs", "/openapi.json", "/ws"]:
            return await call_next(request)

        result = self.limiter.check(request)

        if not result.allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    "X-RateLimit-Limit": str(self.limiter.config.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "60",
                },
            )

        response = await call_next(request)

        # Add rate limit headers with actual remaining values
        response.headers["X-RateLimit-Limit"] = str(self.limiter.config.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining_minute)
        response.headers["X-RateLimit-Hour-Remaining"] = str(result.remaining_hour)

        return response


# API Key authentication
class APIKeyAuth:
    """Simple API key authentication."""

    def __init__(self):
        self._keys: dict[str, dict] = {}  # key -> {name, rate_limit, created}

    def add_key(self, key: str, name: str = "default", rate_limit: int = 60):
        """Add an API key."""
        self._keys[key] = {
            "name": name,
            "rate_limit": rate_limit,
            "created": time.time(),
        }

    def verify(self, key: str | None) -> bool:
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
_rate_limiter: RateLimiter | None = None
_api_auth: APIKeyAuth | None = None


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
    "APIKeyAuth",
    "RateLimitConfig",
    "RateLimitMiddleware",
    "RateLimiter",
    "get_api_auth",
    "get_rate_limiter",
]
