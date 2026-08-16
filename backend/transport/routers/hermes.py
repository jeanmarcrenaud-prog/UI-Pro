"""
Hermes Intelligence Router

Exposes Hermes MCPServer capabilities (execute_intent, read_file, write_file)
as FastAPI endpoints within UI-Pro.
"""

from __future__ import annotations

import logging
import uuid
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
    session_id: str | None = None


class ConversationResponse(BaseModel):
    response: str
    session_id: str | None = None


class ToolRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = {}


class ToolResponse(BaseModel):
    content: str


class CancelRequest(BaseModel):
    session_id: str


class ClearSessionRequest(BaseModel):
    session_id: str

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
        result = await server.call_tool(
            "chat", {"message": req.message, "session_id": req.session_id}
        )
        return ConversationResponse(
            response=result.get("content", ""),
            session_id=result.get("session_id"),
        )
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
    session_id = req.session_id or uuid.uuid4().hex[:12]

    async def event_stream():
        try:
            async for token in server.stream_chat(req.message, session_id):
                # Escape any newlines in token to preserve SSE format
                safe_token = token.replace("\n", "\\n")
                yield f"data: {safe_token}\n\n"
        except Exception as e:
            logger.exception("Hermes stream failed")
            yield f"data: [ERROR] {e}\n\n"

    response = StreamingResponse(event_stream(), media_type="text/event-stream")
    response.headers["X-Session-Id"] = session_id
    return response


@router.post("/conversation/cancel")
async def cancel_conversation(req: CancelRequest) -> dict:
    """Cancel an in-flight Hermes stream for a session."""
    cancelled = get_server().cancel(req.session_id)
    return {"success": cancelled, "session_id": req.session_id}


@router.get("/sessions")
async def list_sessions() -> dict:
    """List active Hermes sessions."""
    return {"sessions": get_server().list_sessions()}


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str) -> dict:
    """Clear a Hermes session's history."""
    cleared = get_server().clear_session(session_id)
    if not cleared:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session_id": session_id}
