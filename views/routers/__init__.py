# views/routers/__init__.py - Router exports
#
# DEPRECATED: Import from backend.transport.routers instead

from backend.transport.routers.health import router as health_router
from backend.transport.routers.ws import router as ws_router
from backend.transport.routers.stream import router as stream_router

__all__ = ["health_router", "ws_router", "stream_router"]