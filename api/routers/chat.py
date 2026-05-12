# api/routers/chat.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.transport.routers.chat instead

from backend.transport.routers.chat import router

__all__ = ["router"]
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