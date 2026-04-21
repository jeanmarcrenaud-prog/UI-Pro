# controllers/websocket.py - WebSocket Controller

import asyncio
import json
from typing import Dict, List

from views.logger import get_logger

logger = get_logger(__name__)


class WebSocketController:
    """Controller for WebSocket streaming - handles all WS logic"""
    
    def __init__(self):
        self.sessions: Dict[str, List[str]] = {}
    
    async def handle_connection(self, ws, client_info: str):
        """Handle new WebSocket connection"""
        session_id = f"{client_info}-{len(self.sessions)}"
        self.sessions[session_id] = []
        logger.info(f"WebSocket connected: {session_id}")
        return session_id
    
    async def handle_message(self, ws, session_id: str, task: str, model: str | None = None):
        """Handle incoming task message"""
        from services.streaming import get_streaming_service
        from settings import settings
        
        if session_id in self.sessions:
            self.sessions[session_id].append(task)
        
        # Model is REQUIRED - no fallback
        if not model:
            raise ValueError("No model provided! Model is required.")
        
        selected_model = model
        
        logger.info(f"Using model: {selected_model} (from user)")
        
        # Stream with proper JSON format - pass model to streaming service
        stream_service = get_streaming_service()
        async for chunk in stream_service.stream_generate(task, model=selected_model):
            await ws.send_text(json.dumps(chunk.to_dict()))
        
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