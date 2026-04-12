# core/events.py - Event Protocol for UI-Pro
"""
Event protocol system with pub/sub for real-time messaging.
Centralizes all event types and handlers.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import uuid

from core.constants import WSEvent, AgentStep


# ==================== Event Classes ====================

@dataclass
class BaseEvent:
    """Base event class with common fields"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "unknown"


@dataclass
class AgentEvent(BaseEvent):
    """Event emitted during agent execution"""
    step: str = AgentStep.ANALYZING
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenEvent(BaseEvent):
    """Token streaming event"""
    token: str = ""
    is_final: bool = False


@dataclass
class ToolEvent(BaseEvent):
    """Tool execution event"""
    tool_name: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Optional[Any] = None
    success: bool = True


@dataclass
class ErrorEvent(BaseEvent):
    """Error event"""
    error_code: str = ""
    message: str = ""
    details: Optional[Dict[str, Any]] = None


# ==================== Event Types Enum ====================

class EventType(str, Enum):
    """All event types in the system"""
    AGENT = "agent"
    TOKEN = "token"
    TOOL = "tool"
    ERROR = "error"
    STATUS = "status"
    HEALTH = "health"


# ==================== Event Bus (Pub/Sub) ====================

class EventBus:
    """Simple pub/sub event bus"""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {
            event_type: [] for event_type in EventType
        }
    
    def subscribe(self, event_type: EventType, handler: Callable) -> str:
        """Subscribe to an event type. Returns subscription ID."""
        sub_id = str(uuid.uuid4())
        self._subscribers[event_type].append(handler)
        return sub_id
    
    def unsubscribe(self, event_type: EventType, handler: Callable):
        """Unsubscribe from an event type"""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
    
    def publish(self, event: BaseEvent, event_type: EventType):
        """Publish an event to all subscribers"""
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                # Log but don't crash
                import logging
                logging.getLogger(__name__).error(f"Handler error: {e}")
    
    def clear(self):
        """Clear all subscribers"""
        for event_type in self._subscribers:
            self._subscribers[event_type].clear()


# Singleton event bus
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create event bus singleton"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# ==================== Event Serializer ====================

def event_to_dict(event: BaseEvent) -> Dict[str, Any]:
    """Serialize event to dict for JSON transmission"""
    return {
        "id": event.id,
        "timestamp": event.timestamp.isoformat(),
        "source": event.source,
        "type": event.__class__.__name__.replace("Event", "").lower(),
    }


def agent_event_to_ws(event: AgentEvent) -> str:
    """Convert AgentEvent to WebSocket message format"""
    return f"[{WSEvent.STEP}]{event.step}:{event.message}"


def token_event_to_ws(event: TokenEvent) -> str:
    """Convert TokenEvent to WebSocket message format"""
    if event.is_final:
        return f"[{WSEvent.DONE}]{event.token}"
    return f"[{WSEvent.TOKEN}]{event.token}"


def tool_event_to_ws(event: ToolEvent) -> str:
    """Convert ToolEvent to WebSocket message format"""
    return f"[{WSEvent.TOOL}]{event.tool_name}"


def error_event_to_ws(event: ErrorEvent) -> str:
    """Convert ErrorEvent to WebSocket message format"""
    return f"[{WSEvent.ERROR}]{event.error_code}:{event.message}"


# ==================== Event Router ====================

class EventRouter:
    """Routes events to appropriate handlers"""
    
    def __init__(self):
        self._routes: Dict[str, Callable] = {}
    
    def register(self, event_type: str, handler: Callable):
        """Register a handler for an event type"""
        self._routes[event_type] = handler
    
    def route(self, event: BaseEvent) -> Optional[str]:
        """Route an event and return result"""
        handler = self._routes.get(event.__class__.__name__)
        if handler:
            return handler(event)
        return None


# ==================== Quick Event Helpers ====================

def emit_agent_step(step: str, message: str, data: Optional[Dict] = None):
    """Quick helper to emit an agent step event"""
    event = AgentEvent(
        step=step,
        message=message,
        data=data or {},
        source="orchestrator"
    )
    get_event_bus().publish(event, EventType.AGENT)
    return event


def emit_token(token: str, is_final: bool = False):
    """Quick helper to emit a token event"""
    event = TokenEvent(
        token=token,
        is_final=is_final,
        source="llm"
    )
    get_event_bus().publish(event, EventType.TOKEN)
    return event


def emit_tool(tool_name: str, input_data: Dict, output_data: Any = None, success: bool = True):
    """Quick helper to emit a tool event"""
    event = ToolEvent(
        tool_name=tool_name,
        input_data=input_data,
        output_data=output_data,
        success=success,
        source="executor"
    )
    get_event_bus().publish(event, EventType.TOOL)
    return event


def emit_error(error_code: str, message: str, details: Optional[Dict] = None):
    """Quick helper to emit an error event"""
    event = ErrorEvent(
        error_code=error_code,
        message=message,
        details=details,
        source="system"
    )
    get_event_bus().publish(event, EventType.ERROR)
    return event