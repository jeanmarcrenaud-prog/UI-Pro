"""API endpoints for per-node pipeline metrics (duration percentiles, token counts).

Endpoints
---------
GET  /api/pipeline/node-metrics       → all nodes
GET  /api/pipeline/node-metrics/{name} → single node
POST /api/pipeline/node-metrics/reset  → clear collected data
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from backend.infrastructure.monitoring.pipeline_metrics_store import (
    get_all_node_metrics,
    get_node_metrics,
    reset_node_metrics,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/node-metrics")
async def list_node_metrics():
    """Return aggregated p50/p95/p99 latency and token counts for *all* nodes."""
    return get_all_node_metrics()


@router.get("/node-metrics/{node_name}")
async def single_node_metrics(node_name: str):
    """Return metrics for a single node (e.g. ``analyzing``)."""
    return get_node_metrics(node_name)


@router.post("/node-metrics/reset")
async def reset_metrics():
    """Reset the in-memory rolling store."""
    reset_node_metrics()
    return {"status": "ok"}
