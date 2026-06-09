"""
Prometheus metrics registry and gauge definitions for GPU and system telemetry.

Exposes:
  - gpu_utilization_percent   — GPU compute utilisation (0-100)
  - gpu_memory_used_bytes     — VRAM used
  - gpu_memory_total_bytes    — VRAM total
  - gpu_temperature_celsius   — GPU temperature
  - cpu_percent               — system CPU usage
  - memory_percent            — system RAM usage

Usage:
    from backend.infrastructure.monitoring.prometheus import (
        get_metrics_registry,
        update_system_metrics,
    )
    # Call update_system_metrics() from a periodic task or health check.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_PROMETHEUS_ENABLED = False

# Lazy-init registry to avoid import-time dependency
_registry: Any = None


def _ensure_registry():
    """Lazy-import prometheus_client and build registry on first use."""
    global _PROMETHEUS_ENABLED, _registry, PROMETHEUS_ENABLED
    if _registry is not None:
        return _registry

    try:
        import prometheus_client  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("prometheus_client not installed — metrics disabled")
        _PROMETHEUS_ENABLED = False
        PROMETHEUS_ENABLED = False
        _registry = None
        return None

    _PROMETHEUS_ENABLED = True
    PROMETHEUS_ENABLED = True
    _registry = prometheus_client.CollectorRegistry()

    # ── GPU metrics ──────────────────────────────────────────────────
    global METRIC_GPU_UTILIZATION, METRIC_GPU_MEMORY_USED
    global METRIC_GPU_MEMORY_TOTAL, METRIC_GPU_TEMPERATURE
    global METRIC_CPU_PERCENT, METRIC_MEMORY_PERCENT

    METRIC_GPU_UTILIZATION = prometheus_client.Gauge(
        "gpu_utilization_percent",
        "GPU compute utilization (0-100)",
        registry=_registry,
    )
    METRIC_GPU_MEMORY_USED = prometheus_client.Gauge(
        "gpu_memory_used_bytes",
        "VRAM currently used in bytes",
        registry=_registry,
    )
    METRIC_GPU_MEMORY_TOTAL = prometheus_client.Gauge(
        "gpu_memory_total_bytes",
        "Total VRAM in bytes",
        registry=_registry,
    )
    METRIC_GPU_TEMPERATURE = prometheus_client.Gauge(
        "gpu_temperature_celsius",
        "GPU temperature in Celsius",
        registry=_registry,
    )
    METRIC_CPU_PERCENT = prometheus_client.Gauge(
        "cpu_percent",
        "System CPU usage percent",
        registry=_registry,
    )
    METRIC_MEMORY_PERCENT = prometheus_client.Gauge(
        "memory_percent",
        "System RAM usage percent",
        registry=_registry,
    )

    return _registry


# Module-level gauge references (populated by _ensure_registry)
METRIC_GPU_UTILIZATION = None
METRIC_GPU_MEMORY_USED = None
METRIC_GPU_MEMORY_TOTAL = None
METRIC_GPU_TEMPERATURE = None
METRIC_CPU_PERCENT = None
METRIC_MEMORY_PERCENT = None


def get_metrics_registry():
    """Return the Prometheus CollectorRegistry (lazy)."""
    return _ensure_registry()


def get_prometheus_enabled() -> bool:
    """Check if prometheus_client was successfully loaded."""
    _ensure_registry()
    return _PROMETHEUS_ENABLED


# Module-level boolean alias (updated by _ensure_registry on first call)
PROMETHEUS_ENABLED: bool = False


def update_system_metrics() -> None:
    """Poll system and GPU metrics and update Prometheus gauges in-place.

    Safe to call from a FastAPI route or background loop — returns
    immediately if prometheus_client is not installed.
    """
    if not _ensure_registry():
        return

    # ── System (CPU / RAM) ───────────────────────────────────────────
    try:
        import psutil

        METRIC_CPU_PERCENT.set(psutil.cpu_percent())  # type: ignore[union-attr]
        METRIC_MEMORY_PERCENT.set(  # type: ignore[union-attr]
            psutil.virtual_memory().percent
        )
    except Exception:
        logger.debug("psutil not available, skipping system metrics")

    # ── GPU (NVML) ───────────────────────────────────────────────────
    try:
        import pynvml  # type: ignore[import-untyped]

        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

        METRIC_GPU_UTILIZATION.set(util.gpu)  # type: ignore[union-attr]
        METRIC_GPU_MEMORY_USED.set(mem_info.used)  # type: ignore[union-attr]
        METRIC_GPU_MEMORY_TOTAL.set(mem_info.total)  # type: ignore[union-attr]

        try:
            temp = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )
            METRIC_GPU_TEMPERATURE.set(temp)  # type: ignore[union-attr]
        except Exception:
            pass
    except ImportError:
        logger.debug("pynvml not installed, skipping GPU metrics")
    except Exception:
        logger.debug("NVML init failed, skipping GPU metrics")


async def generate_metrics_response() -> tuple[str, int, dict[str, str]]:
    """Render /metrics endpoint output.

    Non-blocking variant: ``update_system_metrics()`` is offloaded to a
    thread pool so psutil/pynvml calls don't block the async event loop.

    Returns a (body, status_code, headers) tuple compatible with
    FastAPI ``Response``.
    """
    import asyncio

    reg = _ensure_registry()
    if reg is None:
        return ("# prometheus_client not installed\n", 200, {"content-type": "text/plain"})

    try:
        import prometheus_client  # type: ignore[import-untyped]

        # Offload blocking psutil/pynvml calls to a thread
        await asyncio.to_thread(update_system_metrics)

        body = prometheus_client.generate_latest(reg).decode("utf-8")
        return (body, 200, {"content-type": "text/plain; charset=utf-8"})
    except Exception as exc:
        logger.error("Failed to generate /metrics: %s", exc)
        return (f"# error: {exc}\n", 500, {"content-type": "text/plain"})
