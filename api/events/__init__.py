"""
API Events Configuration - Centralized event management for WebSocket streaming
"""

TYPE_CHOICES = [
    {"step": "Agent phase step (planning, executing, etc.)"},
    {"token": "Streaming token"},
    {"tool": "Tool execution"},
    {"done": "Completion"},
    {"error": "Error event"},
    {"log": "Log stream to other WebSocket clients"}
]

STEP_EVENTS = {
    # Phase 1: Analyzing
    "step-analyzing": {
        "active": {
            "title": "Analyzing request",
            "data": "Analyzing request..."
        },
        "done": {
            "title": "Analyzing request",
            "data": "Analysis complete"
        }
    },
    # Phase 2: Planning
    "step-planning": {
        "active": {
            "title": "Planning solution",
            "data": "Planning approach..."
        },
        "done": {
            "title": "Planning solution",
            "data": "Plan completed"
        }
    },
    # Phase 3: Executing
    "step-executing": {
        "active": {
            "title": "Executing",
            "data": "Executing code..."
        },
        "done": {
            "title": "Executing",
            "data": "Execution complete"
        }
    },
    # Phase 4: Reviewing
    "step-reviewing": {
        "done": {
            "title": "Reviewing",
            "data": "Review complete"
        }
    },
    # Note: no active state for step-reviewing, just done
}

# Default events
DONE_EVENT = {"type": "done", "data": ""}
ERROR_EVENT = {"type": "error", "data": ""}