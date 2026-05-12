# core/events.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.domain.core.events instead

from backend.domain.core.events import (
    BaseEvent,
    AgentEvent,
    TokenEvent,
    ToolEvent,
    ErrorEvent,
    EventType,
    EventBus,
    get_event_bus,
    event_to_dict,
    agent_event_to_ws,
    token_event_to_ws,
    tool_event_to_ws,
    error_event_to_ws,
    EventRouter,
    emit_agent_step,
    emit_token,
    emit_tool,
    emit_error,
)

__all__ = [
    "BaseEvent",
    "AgentEvent",
    "TokenEvent",
    "ToolEvent",
    "ErrorEvent",
    "EventType",
    "EventBus",
    "get_event_bus",
    "event_to_dict",
    "agent_event_to_ws",
    "token_event_to_ws",
    "tool_event_to_ws",
    "error_event_to_ws",
    "EventRouter",
    "emit_agent_step",
    "emit_token",
    "emit_tool",
    "emit_error",
]