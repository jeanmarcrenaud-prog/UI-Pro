# views/routers/stream.py - SSE Streaming Endpoints (Unified Protocol)

import logging

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel

from backend.domain.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stream"])

# Import unified streaming
from backend.domain.core.langgraph.streaming import get_stream_checkpoint
from backend.infrastructure.streaming import create_sse_response


class StreamRequest(BaseModel):
    message: str
    model: str | None = None
    provider: str | None = "ollama"
    temperature: float | None = 0.7
    session_id: str | None = None
    resume_from: str | None = None  # stream_id to resume from


class ResumeRequest(BaseModel):
    stream_id: str
    message: str
    model: str | None = None
    provider: str | None = "ollama"


@router.get("/stream")
@router.get("/api/stream")
async def stream_endpoint_get(
    prompt: str = Query(..., description="The prompt to send"),
    model: str = Query(None, description="Model to use"),
    provider: str = Query("ollama", description="Backend provider"),
    temperature: float = Query(0.7, ge=0.0, le=2.0),
    session_id: str = Query(None, description="Session ID for resume"),
    resume_from: str = Query(None, description="Stream ID to resume from"),
):
    """Server-Sent Events streaming endpoint (GET) - Unified Protocol"""
    if not model:
        model = settings.model_fast or "qwen3.5:0.8b"

    # Strip provider prefix from model name
    if model and provider and model.startswith(f"{provider}-"):
        model = model[len(provider) + 1 :]

    return await create_sse_response(
        message=prompt,
        model=model,
        provider=provider,
        temperature=temperature,
        session_id=session_id,
        resume_from=resume_from,
    )


@router.post("/stream")
@router.post("/api/stream")
async def stream_endpoint_post(request: StreamRequest = Body(...)):
    """Server-Sent Events streaming endpoint (POST) - Unified Protocol"""
    model = request.model or settings.model_fast or "qwen3.5:0.8b"
    provider = request.provider or "ollama"

    # Strip provider prefix from model name
    if model and provider and model.startswith(f"{provider}-"):
        model = model[len(provider) + 1 :]

    return await create_sse_response(
        message=request.message,
        model=model,
        provider=provider,
        temperature=request.temperature or 0.7,
        session_id=request.session_id,
        resume_from=request.resume_from,
    )


@router.post("/stream/resume")
@router.post("/api/stream/resume")
async def stream_resume(request: ResumeRequest = Body(...)):
    """Resume a stream from checkpoint - Unified Protocol"""
    checkpoint = get_stream_checkpoint(request.stream_id)
    if not checkpoint:
        return {"error": "Stream not found or expired", "stream_id": request.stream_id}

    model = request.model or settings.model_fast or "qwen3.5:0.8b"

    return await create_sse_response(
        message=request.message,
        model=model,
        provider=request.provider or "ollama",
        temperature=0.7,
        session_id=checkpoint["session_id"],
        resume_from=request.stream_id,
    )


@router.get("/stream/checkpoint/{stream_id}")
@router.get("/api/stream/checkpoint/{stream_id}")
async def get_checkpoint(stream_id: str):
    """Get checkpoint info for a stream."""
    from backend.domain.core.langgraph.streaming import get_stream_checkpoint

    checkpoint = get_stream_checkpoint(stream_id)
    if not checkpoint:
        return {"error": "Stream not found", "stream_id": stream_id}

    return {
        "stream_id": stream_id,
        "last_token_index": checkpoint["last_token_index"],
        "session_id": checkpoint["session_id"],
        "timestamp": checkpoint["timestamp"],
    }
