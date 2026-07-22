"""
Hermes Intelligence Router

Exposes Hermes MCPServer capabilities (execute_intent, read_file, write_file)
as FastAPI endpoints within UI-Pro.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hermes", tags=["hermes"])

_server_instance: Any = None


def _get_server():
    global _server_instance
    if _server_instance is None:
        from backend.infrastructure.mcp.server import HermesMCPServer
        _server_instance = HermesMCPServer()
    return _server_instance

# ─── Models ─────────────────────────────────────


class ConversationRequest(BaseModel):
    message: str
    context: str = ""


class ConversationResponse(BaseModel):
    response: str


class ToolRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = {}


class ToolResponse(BaseModel):
    content: str


# ─── Endpoints ─────────────────────────────────


@router.get("/status")
async def get_status() -> dict:
    """Check if Hermes is available."""
    return {
        "available": True,
        "tools": _get_server().list_tools(),
    }


@router.post("/conversation", response_model=ConversationResponse)
async def conversation(req: ConversationRequest) -> ConversationResponse:
    """Send a message to Hermes and get a chat response."""
    server = _get_server()
    try:
        result = await server.call_tool("chat", {"message": req.message})
        return ConversationResponse(response=result.get("content", ""))
    except Exception as e:
        logger.exception("Hermes chat failed")
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/tool", response_model=ToolResponse)
async def run_tool(req: ToolRequest) -> ToolResponse:
    """Execute a specific Hermes tool by name."""
    server = _get_server()
    result = await server.call_tool(req.tool, req.arguments)
    return ToolResponse(content=result.get("content", str(result)))
