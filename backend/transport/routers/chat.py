# api/routers/chat.py - Chat endpoint (REST fallback)
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
import logging

from settings import settings

router = APIRouter(prefix="/api", tags=["chat"])

logger = logging.getLogger(__name__)

API_KEY_HEADER = "x-api-key"


def verify_api_key(request: Request):
    api_key = getattr(settings, "api_key", None)
    if not api_key:
        return True
    if request.headers.get(API_KEY_HEADER) != api_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    provider: Optional[str] = None  # ollama, lmstudio, lemonade, llamacpp


class ChatResponse(BaseModel):
    result: str
    status: str = "success"


@router.post("/chat", dependencies=[Depends(verify_api_key)])
async def chat(request: ChatRequest):
    """Chat endpoint (REST fallback when WebSocket fails)"""
    try:
        logger.debug(f"[CHAT] Request: message={request.message[:50]}... model={request.model} provider={request.provider}")

        from backend.infrastructure.streaming import get_streaming_service
        stream_service = get_streaming_service()

        # Collect full response from streaming (async)
        chunks = []
        async for chunk in stream_service.stream_generate(
            request.message,
            model=request.model or settings.model_fast,
            provider=request.provider
        ):
            if chunk.text:
                chunks.append(chunk.text)

        result_text = "".join(chunks)
        logger.info(f"[CHAT] Response generated: {len(result_text)} characters")
        return ChatResponse(result=result_text, status="success")

    except Exception as e:
        logger.error(f"[CHAT] Error: {type(e).__name__}: {str(e)}")
        return ChatResponse(result=f"Error: {str(e)}", status="error")


@router.post("/stream", dependencies=[Depends(verify_api_key)])
async def stream(request: ChatRequest):
    """SSE streaming endpoint (fallback when WebSocket fails)"""
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            logger.debug(f"[STREAM] Starting stream: message={request.message[:50]}... model={request.model}")

            from backend.infrastructure.streaming import get_streaming_service
            stream_service = get_streaming_service()

            chunk_count = 0
            async for chunk in stream_service.stream_generate(
                request.message,
                model=request.model or settings.model_fast,
                provider=request.provider
            ):
                if chunk.text:
                    chunk_count += 1
                    yield f"data: {{'content': '{chunk.text.replace(chr(10), ' ')}', 'done': false}}\n\n"

            logger.info(f"[STREAM] Completed: {chunk_count} chunks sent")
            yield "data: {'done': true}\n\n"
        except Exception as e:
            logger.error(f"[STREAM] Error: {type(e).__name__}: {str(e)}")
            yield f"data: {{'error': '{str(e)}', 'done': true}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")