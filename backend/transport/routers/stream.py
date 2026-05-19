# views/routers/stream.py - SSE Streaming Endpoints

from fastapi import APIRouter, Query, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import logging
import uuid

from models.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stream"])


async def sse_generator(prompt: str, model: str, provider: str, temperature: float, session_id: Optional[str] = None):
    """Generate SSE events from LangGraph streaming."""
    import asyncio
    from backend.domain.core.langgraph.streaming import stream_agent
    
    session_id = session_id or str(uuid.uuid4())[:8]
    message_id = str(uuid.uuid4())
    
    # Token buffer for chunking (5-8 tokens accumulated before sending)
    token_buffer = ""
    CHUNK_SIZE = 5  # Send after accumulating 5 tokens
    
    try:
        async for event in stream_agent(
            message=prompt,
            session_id=session_id,
            model=model,
            provider=provider,
        ):
            # Parse events from stream_agent
            if event.startswith("[STEP]"):
                parts = event[6:].split(":", 1)
                phase = parts[0] if parts else "step"
                content = parts[1] if len(parts) > 1 else ""
                
                yield f"data: {json.dumps({
                    'type': 'step',
                    'step_id': f'step-{phase}',
                    'title': phase.replace('_', ' ').title(),
                    'status': 'active',
                    'message_id': message_id,
                    'content': content
                })}\n\n"
                
            elif event.startswith("[TOKEN]"):
                token_buffer += event[7:]
                
                # Send chunk when buffer reaches threshold
                if len(token_buffer) >= CHUNK_SIZE * 4:  # ~4 chars per token
                    yield f"data: {json.dumps({
                        'type': 'token',
                        'content': token_buffer,
                        'response': token_buffer,
                        'done': False,
                        'message_id': message_id,
                        'token_count': len(token_buffer) // 2
                    })}\n\n"
                    token_buffer = ""
                    
            elif event.startswith("[TOOL]"):
                parts = event[6:].split(":", 1)
                action = parts[0] if parts else "tool"
                content = parts[1] if len(parts) > 1 else ""
                
                yield f"data: {json.dumps({
                    'type': 'step',
                    'step_id': f'tool-{action}',
                    'title': action.replace('_', ' ').title(),
                    'status': 'done',
                    'message_id': message_id,
                    'content': content
                })}\n\n"
                
            elif event.startswith("[ERROR]"):
                parts = event[7:].split(":", 1)
                code = parts[0] if parts else "500"
                content = parts[1] if len(parts) > 1 else ""
                
                yield f"data: {json.dumps({
                    'type': 'error',
                    'message': content,
                    'code': code,
                    'message_id': message_id
                })}\n\n"
                
            elif event == "[DONE]":
                # Flush remaining tokens
                if token_buffer:
                    yield f"data: {json.dumps({
                        'type': 'token',
                        'content': token_buffer,
                        'response': token_buffer,
                        'done': False,
                        'message_id': message_id,
                        'token_count': len(token_buffer) // 2
                    })}\n\n"
                
                yield f"data: {json.dumps({
                    'type': 'done',
                    'message_id': message_id
                })}\n\n"
                
    except Exception as e:
        logger.error(f"SSE streaming error: {e}")
        yield f"data: {json.dumps({
            'type': 'error',
            'message': str(e),
            'code': '500',
            'message_id': message_id
        })}\n\n"
        yield f"data: {json.dumps({
            'type': 'done',
            'message_id': message_id
        })}\n\n"


class StreamRequest(BaseModel):
    message: str
    model: Optional[str] = None
    provider: Optional[str] = "ollama"
    temperature: Optional[float] = 0.7
    session_id: Optional[str] = None


@router.get("/stream")
@router.get("/api/stream")
async def stream_endpoint_get(
    prompt: str = Query(..., description="The prompt to send"),
    model: str = Query(None, description="Model to use"),
    provider: str = Query("ollama", description="Backend provider"),
    temperature: float = Query(0.7, ge=0.0, le=2.0),
    session_id: str = Query(None, description="Session ID for resume"),
):
    """Server-Sent Events streaming endpoint (GET)"""
    if not model:
        model = settings.model_fast or "qwen3.5:0.8b"

    return StreamingResponse(
        sse_generator(prompt, model, provider, temperature, session_id),
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
        sse_generator(request.message, model, request.provider or "ollama", request.temperature or 0.7, request.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )