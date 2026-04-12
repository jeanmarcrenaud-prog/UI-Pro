# controllers/websocket.py - WebSocket Controller

import asyncio
import io
import sys
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
        if session_id in self.sessions:
            self.sessions[session_id].append(task)
        
        # Process task with streaming
        result = await self._process_task(task)
        
        # Send streaming results
        for line in result.split("\n"):
            if line.strip():
                await ws.send_text(line)
        
        # Send completion marker
        await ws.send_text("[DONE]")
        
        return result
    
    async def _process_task(self, task: str) -> str:
        """Process task with stream capture"""
        # Import here to avoid circular imports
        from controllers.team import run_team
        
        # Capture stdout
        buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buffer
        
        try:
            # Run the task
            result = run_team(task)
        finally:
            sys.stdout = old_stdout
        
        return buffer.getvalue()
    
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