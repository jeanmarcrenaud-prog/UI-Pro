# api/dashboard.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.transport.dashboard instead

from backend.transport.dashboard import create_dashboard, run

__all__ = ["create_dashboard", "run"]