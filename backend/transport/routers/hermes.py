"""
Hermes Intelligence Router

Exposes Hermes MCPServer capabilities (execute_intent, read_file, write_file)
as FastAPI endpoints within UI-Pro.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hermes", tags=["hermes"])

from backend.infrastructure.mcp.server import get_server


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
        "tools": get_server().list_tools(),
    }


@router.post("/conversation", response_model=ConversationResponse)
async def conversation(req: ConversationRequest) -> ConversationResponse:
    """Send a message to Hermes and get a chat response."""
    server = get_server()
    try:
        result = await server.call_tool("chat", {"message": req.message})
        return ConversationResponse(response=result.get("content", ""))
    except Exception as e:
        logger.exception("Hermes chat failed")
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/tool", response_model=ToolResponse)
async def run_tool(req: ToolRequest) -> ToolResponse:
    """Execute a specific Hermes tool by name."""
    server = get_server()
    result = await server.call_tool(req.tool, req.arguments)
    return ToolResponse(content=result.get("content", str(result)))


@router.post("/conversation/stream")
async def conversation_stream(req: ConversationRequest):
    """Stream Hermes chat response token-by-token via SSE."""
    server = get_server()

    async def event_stream():
        async for token in server.stream_chat(req.message):
            yield f"data: {token}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
