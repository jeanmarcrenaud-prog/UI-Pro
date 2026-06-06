"""Health check utilities for LLM backends."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


def check_backend_health(url: str, timeout: float = 5.0) -> dict:
    """Quick health check for a single backend endpoint.

    Returns:
        {"status": "ok"|"error", "latency_ms": float, "error": str|None}
    """
    start = time.monotonic()
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        ms = round((time.monotonic() - start) * 1000, 1)
        return {"status": "ok", "latency_ms": ms, "error": None}
    except requests.RequestException as e:
        ms = round((time.monotonic() - start) * 1000, 1)
        return {"status": "error", "latency_ms": ms, "error": str(e)}


def check_ollama_version(ollama_url: str, timeout: float = 5.0) -> dict:
    """Probe Ollama's /api/version endpoint for diagnostic info.

    Returns a dict with:
        - status: "ok" | "error" | "unknown"
        - version: the reported Ollama version string (or None on failure)
        - latency_ms: round-trip in ms
        - error: error string or None

    Ollama exposes /api/version since v0.1.14. Older installs return 404,
    which is treated as "unknown" rather than a hard error so deployments
    on older versions don't get a false alarm.
    """
    base = ollama_url.rstrip("/")
    # ollama_url is often the chat URL (e.g. http://localhost:11434). Trim
    # any /api/* suffix so we hit the version root.
    for suffix in ("/api/generate", "/api/chat", "/api/tags"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    version_url = f"{base}/api/version"
    start = time.monotonic()
    try:
        resp = requests.get(version_url, timeout=timeout)
        ms = round((time.monotonic() - start) * 1000, 1)
        if resp.status_code == 404:
            return {
                "status": "unknown",
                "version": None,
                "latency_ms": ms,
                "error": "Ollama /api/version not available (older version?)",
            }
        resp.raise_for_status()
        data = resp.json()
        return {
            "status": "ok",
            "version": data.get("version"),
            "latency_ms": ms,
            "error": None,
        }
    except requests.RequestException as e:
        ms = round((time.monotonic() - start) * 1000, 1)
        return {
            "status": "error",
            "version": None,
            "latency_ms": ms,
            "error": str(e),
        }


def check_backends_parallel(
    endpoints: dict[str, str], timeout: float = 5.0
) -> dict[str, dict]:
    """Run health checks for multiple backends in parallel.

    Args:
        endpoints: dict of {backend_name: health_url}
        timeout: per-request timeout

    Returns:
        dict of {backend_name: {"status": ..., "latency_ms": ..., "error": ...}}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[str, dict] = {}

    def _check(name: str, url: str) -> tuple[str, dict]:
        return name, check_backend_health(url, timeout)

    with ThreadPoolExecutor(max_workers=len(endpoints) or 1) as pool:
        futures = {
            pool.submit(_check, name, url): name for name, url in endpoints.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                _, result = future.result()
                results[name] = result
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "latency_ms": 0,
                    "error": str(e),
                }

    return results


def aggregate_health(results: dict[str, dict]) -> dict[str, Any]:
    """Summarize multiple backend health results.

    Returns:
        {"status": "ok"|"degraded"|"error",
         "backends": list,
         "details": dict,
         "ok_count": int,
         "error_count": int}
    """
    ok_count = sum(
        1 for r in results.values() if r.get("status") == "ok"
    )
    total = len(results)

    if ok_count == total:
        status = "ok"
    elif ok_count > 0:
        status = "degraded"
    else:
        status = "error"

    return {
        "status": status,
        "backends": sorted(results),
        "details": results,
        "ok_count": ok_count,
        "error_count": total - ok_count,
    }


__all__ = [
    "aggregate_health",
    "check_backend_health",
    "check_backends_parallel",
    "check_ollama_version",
]
