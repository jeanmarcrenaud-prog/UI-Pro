# controllers/websocket.py - WebSocket Controller

import asyncio
import json
from typing import Dict, List

from views.logger import get_logger
from models.settings import settings

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
    
    async def handle_message(self, ws, session_id: str, task: str):
        """Handle incoming task message"""
        import json
        from services.streaming import get_streaming_service
        
        if session_id in self.sessions:
            self.sessions[session_id].append(task)
        
        # Use StreamingService for proper JSON streaming
        stream_service = get_streaming_service()
        
        # Stream with proper JSON format
        async for chunk in stream_service.stream_generate(task):
            # Send as JSON
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