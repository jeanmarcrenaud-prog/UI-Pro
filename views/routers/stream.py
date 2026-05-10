# views/routers/stream.py - Streaming endpoints (SSE)

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import logging

from models.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["stream"])


def _get_streaming_service_cached():
    """Get streaming service with caching."""
    from functools import lru_cache
    
    @lru_cache()
    def get_service():
        from services.streaming import get_streaming_service
        return get_service()
    
    return get_service()


async def generate_sse(prompt: str, model: str, provider: str = "ollama", temperature: float = 0.7):
    """Generate SSE stream."""
    stream_service = _get_streaming_service_cached()
    
    async for chunk in stream_service.stream_generate(
        prompt=prompt,
        model=model,
        provider=provider,
        temperature=temperature
    ):
        chunk_data = chunk.to_dict()
        yield f"data: {chunk_data}\n\n"


@router.get("/stream")
@router.get("/api/stream")
async def stream_endpoint(
    prompt: str = Query(..., description="Prompt to generate from"),
    model: str = Query(settings.model_fast or "qwen3.5:0.8b", description="Model to use"),
    provider: str = Query("ollama", description="Provider (ollama, lmstudio, lemonade)"),
    temperature: float = Query(0.7, description="Temperature for generation")
):
    """SSE streaming endpoint."""
    return StreamingResponse(
        generate_sse(prompt, model, provider, temperature),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )