"""
backend/infrastructure/cache.py - Generic TTL Cache

Provides a thread-safe TTL cache with LRU eviction for expensive
operations like model discovery, LLM calls, and API requests.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class TTLCache:
    """Thread-safe TTL cache with LRU eviction.

    Usage:
        cache = TTLCache[str, list](maxsize=128, ttl=30)
        cache.set("models", result)
        cached = cache.get("models")  # returns None if expired/missing
    """

    def __init__(self, maxsize: int = 128, ttl: float = 30.0):
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        """Get cached value. Returns None if missing or expired."""
        if key not in self._cache:
            return None
        expires_at, value = self._cache[key]
        if time.monotonic() > expires_at:
            del self._cache[key]
            return None
        # LRU: move to end (most recently used)
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set cached value with optional per-key TTL."""
        expires_at = time.monotonic() + (ttl if ttl is not None else self._ttl)
        self._cache[key] = (expires_at, value)
        self._cache.move_to_end(key)
        self._evict()

    def delete(self, key: str) -> None:
        """Remove a specific key from cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def _evict(self) -> None:
        """Evict oldest entries if over maxsize."""
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def is_empty(self) -> bool:
        return len(self._cache) == 0


def cached(
    ttl: float = 30.0,
    maxsize: int = 128,
    key_builder: Callable[..., str] | None = None,
) -> Callable:
    """Decorator that caches function results with TTL.

    Usage:
        @cached(ttl=60.0)
        def expensive_func(arg1, arg2):
            ...

    The cache key is built from the function name + repr(args) by default.
    Pass `key_builder` for custom key logic.
    """
    # Per-function cache (shared across all calls)
    cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                key = f"{func.__name__}:{args!r}:{kwargs!r}"
            result = cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator
