# controllers/websocket.py - WebSocket Controller

import asyncio
import json
from typing import Dict, List

from core.logger import get_logger

logger = get_logger(__name__)


class WebSocketController:
    """Controller for WebSocket streaming - handles all WS logic"""
    
    def __init__(self):
        # sessions: {session_id: {'tasks': []}}
        self.sessions: Dict[str, dict] = {}
        # Store model per client IP (persistent across reconnections)
        self.client_models: Dict[str, str] = {}
    
    async def handle_connection(self, ws, client_info: str):
        """Handle new WebSocket connection"""
        session_id = f"{client_info}-{len(self.sessions)}"
        self.sessions[session_id] = {'tasks': []}
        logger.info(f"WebSocket connected: {session_id}")
        return session_id
    
    async def handle_message(self, ws, session_id: str, task: str, model: str | None = None):
        """Handle incoming task message"""
        from services.streaming import get_streaming_service
        
        # Extract client IP from session_id
        client_ip = session_id.split('-')[0] if '-' in session_id else session_id
        
        # Store task
        if session_id in self.sessions:
            self.sessions[session_id]['tasks'].append(task)
        
        # If model provided, store it for THIS CLIENT (persist across reconnections!)
        if model:
            self.client_models[client_ip] = model
            logger.info(f"Model stored for {client_ip}: {model}")
        
        # Use stored model for this client if no new model provided
        if not model:
            model = self.client_models.get(client_ip)
        
        # Model is REQUIRED - no fallback
        if not model:
            raise ValueError("No model provided! Model is required.")
        
        logger.info(f"Using model: {model}")
        
        # Stream with proper JSON format - pass model to streaming service
        logger.info(f"[WS] Starting stream_generate for task: {task[:50]}...")
        stream_service = get_streaming_service()
        logger.info(f"[WS] Got stream service, about to iterate...")
        chunk_count = 0
        async for chunk in stream_service.stream_generate(task, model=model):
            logger.info(f"[WS] Got chunk from stream, about to send...")
            await ws.send_text(json.dumps(chunk.to_dict()))
            chunk_count += 1
            logger.info(f"[WS] Sent chunk {chunk_count}: {chunk.status}")
        
        logger.info(f"[WS] Stream complete, sent {chunk_count} chunks")
        
        return ""
    
    async def handle_disconnect(self, session_id: str):
        """Handle disconnection"""
        if session_id in self.sessions:
            del self.sessions[session_id]
        logger.info(f"WebSocket disconnected: {session_id}")


# Singleton instance
_websocket_controller = None


def get_websocket_controller() -> WebSocketController:
    """Get or create WebSocket controller singleton"""
    global _websocket_controller
    if _websocket_controller is None:
        _websocket_controller = WebSocketController()
    return _websocket_controller