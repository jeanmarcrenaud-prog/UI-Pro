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
]
