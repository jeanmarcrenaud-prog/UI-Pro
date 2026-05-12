# core/state_manager.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.domain.core.state_manager instead

from backend.domain.core.state_manager import (
    State,
    StateManager,
    init_state,
    save_state,
    load_state,
)

__all__ = [
    "State",
    "StateManager",
    "init_state",
    "save_state",
    "load_state",
]