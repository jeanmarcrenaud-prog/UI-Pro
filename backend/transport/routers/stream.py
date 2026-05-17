# views/routers/stream.py - SSE Streaming Endpoints

from fastapi import APIRouter, Query, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import logging

from models.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stream"])


def _get_streaming_service():
    from backend.infrastructure.streaming import get_streaming_service
    return get_streaming_service()


async def sse_generator(prompt: str, model: str, provider: str, temperature: float):
    stream_service = _get_streaming_service()
    async for chunk in stream_service.stream_generate(
        prompt=prompt,
        model=model,
        provider=provider,
        temperature=temperature
    ):
        yield f"data: {json.dumps(chunk.to_dict())}\n\n"


class StreamRequest(BaseModel):
    message: str
    model: Optional[str] = None
    provider: Optional[str] = "ollama"
    temperature: Optional[float] = 0.7


@router.get("/stream")
@router.get("/api/stream")
async def stream_endpoint_get(
    prompt: str = Query(..., description="The prompt to send"),
    model: str = Query(None, description="Model to use"),
    provider: str = Query("ollama", description="Backend provider"),
    temperature: float = Query(0.7, ge=0.0, le=2.0),
):
    """Server-Sent Events streaming endpoint (GET)"""
    if not model:
        model = settings.model_fast or "qwen3.5:0.8b"

    return StreamingResponse(
        sse_generator(prompt, model, provider, temperature),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/stream")
@router.post("/api/stream")
async def stream_endpoint_post(request: StreamRequest = Body(...)):
    """Server-Sent Events streaming endpoint (POST)"""
    model = request.model or settings.model_fast or "qwen3.5:0.8b"

    return StreamingResponse(
        sse_generator(request.message, model, request.provider or "ollama", request.temperature or 0.7),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )