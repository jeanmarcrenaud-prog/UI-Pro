# api/routers/chat.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.transport.routers.chat instead

from backend.transport.routers.chat import router

__all__ = ["router"]