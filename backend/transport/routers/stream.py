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

# Import at module level for LSP
from backend.domain.core.langgraph.streaming import stream_agent, get_stream_checkpoint


async def sse_generator(prompt: str, model: str, provider: str, temperature: float, session_id: Optional[str] = None, resume_from: Optional[str] = None):
    """Generate SSE events from LangGraph streaming."""
    import asyncio
    from backend.domain.core.langgraph.streaming import stream_agent
    
    session_id = session_id or str(uuid.uuid4())[:8]
    message_id = str(uuid.uuid4())
    stream_id = None
    
    # Token buffer for chunking (5-8 tokens accumulated before sending)
    token_buffer = ""
    CHUNK_SIZE = 5  # Send after accumulating 5 tokens
    
    try:
        async for event in stream_agent(
            message=prompt,
            session_id=session_id,
            model=model,
            provider=provider,
            resume_from=resume_from,
        ):
            # Parse events from stream_agent
            # Handle stream_id event
            if event.startswith("[STREAM_ID]"):
                stream_id = event[11:]  # Extract stream_id
                yield f"data: {json.dumps({
                    'type': 'stream_id',
                    'stream_id': stream_id,
                    'message_id': message_id
                })}\n\n"
                continue
                
            # Handle resume acknowledgment
            if event.startswith("[RESUME]"):
                # Format: [RESUME]stream_id:from_index:X
                parts = event[7:].split(":")
                resumed_stream_id = parts[0] if len(parts) > 0 else ""
                from_index = int(parts[2]) if len(parts) > 2 else 0
                yield f"data: {json.dumps({
                    'type': 'resumed',
                    'stream_id': resumed_stream_id,
                    'from_index': from_index,
                    'message_id': message_id
                })}\n\n"
                continue
                
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
    resume_from: Optional[str] = None  # stream_id to resume from


class ResumeRequest(BaseModel):
    stream_id: str
    message: str
    model: Optional[str] = None
    provider: Optional[str] = "ollama"


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
    """Server-Sent Events streaming endpoint (GET)"""
    if not model:
        model = settings.model_fast or "qwen3.5:0.8b"

    return StreamingResponse(
        sse_generator(prompt, model, provider, temperature, session_id, resume_from),
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
        sse_generator(request.message, model, request.provider or "ollama", request.temperature or 0.7, request.session_id, request.resume_from),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/stream/resume")
@router.post("/api/stream/resume")
async def stream_resume(request: ResumeRequest = Body(...)):
    """Resume a stream from checkpoint."""
    from backend.domain.core.langgraph.streaming import get_stream_checkpoint
    
    checkpoint = get_stream_checkpoint(request.stream_id)
    if not checkpoint:
        return {"error": "Stream not found or expired", "stream_id": request.stream_id}
    
    model = request.model or settings.model_fast or "qwen3.5:0.8b"
    
    return StreamingResponse(
        sse_generator(
            request.message, 
            model, 
            request.provider or "ollama", 
            0.7, 
            checkpoint["session_id"], 
            request.stream_id  # resume_from
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
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