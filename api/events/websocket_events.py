"""
WebSocket Events Constants - DEDUPED from main.py

Extracted all duplicated step event patterns into centralized constants
"""

import json
from typing import Dict, Any

# ==================== STEP EVENTS ====================

# Step configuration for each agent phase
STEP_EVENTS: Dict[str, Dict[str, str]] = {
    "step-analyzing": {
        "active": {
            "type": "step",
            "step_id": "step-analyzing",
            "title": "Analyzing request",
            "status": "active",
            "data": "Analyzing request..."
        },
        "done": {
            "type": "step",
            "step_id": "step-analyzing",
            "title": "Analyzing request",
            "status": "done",
            "data": "Analysis complete"
        }
    },
    "step-planning": {
        "active": {
            "type": "step",
            "step_id": "step-planning",
            "title": "Planning solution",
            "status": "active",
            "data": "Planning approach..."
        },
        "done": {
            "type": "step",
            "step_id": "step-planning",
            "title": "Planning solution",
            "status": "done",
            "data": "Plan completed"
        }
    },
    "step-executing": {
        "active": {
            "type": "step",
            "step_id": "step-executing",
            "title": "Executing",
            "status": "active",
            "data": "Executing code..."
        },
        "done": {
            "type": "step",
            "step_id": "step-executing",
            "title": "Executing",
            "status": "done",
            "data": "Execution complete"
        }
    },
    "step-reviewing": {
        "done": {
            "type": "step",
            "step_id": "step-reviewing",
            "title": "Reviewing",
            "status": "done",
            "data": "Review complete"
        }
    }
}

# Default done event
DONE_EVENT = {"type": "done", "data": ""}

# Log event template
LOG_EVENT_TEMPLATE = {
    "type": "log",
    "message": "{message}",
    "status": "{status}"
}

# ==================== HELPER FUNCTIONS ====================

def send_step_event(step_id: str, status: str, data: str = "") -> Dict[str, Any]:
    """
    Send a step event with correct title from STEP_EVENTS
    
    This dedupes the 4 duplicated send_text blocks in main.py
    """
    event_data = STEP_EVENTS.get(step_id, {}).get(status)
    
    if event_data:
        return event_data
    else:
        # Fallback for unknown step/status
        return {
            "type": "step",
            "step_id": step_id,
            "status": status,
            "data": data
        }


def send_done_event() -> Dict[str, str]:
    """Send done event - deduped from line 333"""
    return json.dumps(DONE_EVENT)


def send_log_event(message: str, status: str) -> Dict[str, Any]:
    """
    Send log event to other WebSocket subscribers
    
    Dedupes the pattern from lines 286-294:
    ```
    await log_ws.send_text(json.dumps({
        "type": "log",
        "message": chunk.text[:100] if chunk.text else "",
        "status": chunk.status.value
    }))
    ```
    """
    safe_message = message[:100] if message else ""
    # Extract status value (handle status enum)
    status_value = status if isinstance(status, str) else str(status.value) if hasattr(status, 'value') else status
    
    return json.dumps({
        "type": "log",
        "message": safe_message,
        "status": status_value
    })


# ==================== USAGE EXAMPLE ====================

# Old code (Duplicated):
# await ws.send_text(json.dumps({
#     "type": "step",
#     "step_id": "step-analyzing",
#     "title": "Analyzing request",
#     "status": "done",
#     "data": "Analysis complete"
# }))
# 
# New code (Deduped):
# event_data = send_step_event("step-analyzing", "done")
# await ws.send_text(json.dumps(event_data))
