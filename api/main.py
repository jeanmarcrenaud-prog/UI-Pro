# api/main.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.transport.main instead

from backend.transport.main import app

__all__ = ["app"]