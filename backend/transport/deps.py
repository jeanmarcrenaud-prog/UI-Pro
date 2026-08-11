# transport/deps.py - Shared FastAPI dependencies
"""Shared FastAPI dependencies (authentication, common helpers).

Routers must import ``verify_api_key`` from here instead of re-defining it,
so API-key enforcement stays consistent across endpoints.
"""

from fastapi import HTTPException, Request

from backend.domain.settings import settings

API_KEY_HEADER = "x-api-key"


def verify_api_key(request: Request):
    """Reject requests that don't match the configured API key.

    When no API key is configured, every request is allowed.
    """
    api_key = getattr(settings, "api_key", None)
    if not api_key:
        return True
    if request.headers.get(API_KEY_HEADER) != api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True