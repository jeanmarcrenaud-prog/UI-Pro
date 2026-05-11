# api/routers/chat.py - Chat endpoint (REST fallback)
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional
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
        return ChatResponse(result=result_text, status="success")

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return ChatResponse(result=f"Error: {str(e)}", status="error")