# core/ - Backward Compatibility Re-exports
#
# DEPRECATED: Import from backend.domain.core.* instead

from backend.domain.core.executor import CodeExecutor, ExecutionConfig
from backend.domain.core.constants import WSEvent, AgentStep, ErrorCode, ConfigKey
from backend.domain.core.orchestrator_async import Orchestrator
from backend.domain.core.prompts import (
    SYSTEM_PLANNER,
    SYSTEM_ARCHITECT,
    SYSTEM_CODER,
    SYSTEM_REVIEWER,
    SYSTEM_FIXER,
    PLANNER_PROMPT,
    ARCHITECT_PROMPT,
    CODER_PROMPT,
    REVIEWER_PROMPT,
    FIX_PROMPT,
    MEMORY_CONTEXT_PROMPT,
    PROMPTS,
    SYSTEMS,
    format_with_fallback,
    get_prompt,
    planner_prompt,
    architect_prompt,
    coder_prompt,
    reviewer_prompt,
    fix_prompt,
)
from backend.domain.core.state_manager import State, StateManager, init_state, save_state, load_state
from backend.domain.core.code_review import ReviewResult, CodeReviewer, get_reviewer, review_code
from backend.domain.core.logger import (
    JSONFormatter,
    LoggerManager,
    set_correlation_id,
    get_correlation_id,
    generate_correlation_id,
    get_logger,
    debug,
    info,
    warning,
    error,
    critical,
    log_performance,
)
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
from backend.domain.core.metrics import (
    ExecutionRecord,
    Metrics,
    MetricsManager,
    get_metrics_manager,
    record_execution,
    get_metrics,
    get_dashboard_data,
)

# Also re-export from other backend locations
from backend.infrastructure.memory import (
    MemoryManager,
    get_memory_manager,
    add_memory,
    search_memory,
    MockLogger,
)

try:
    from backend.infrastructure.memory import model as _memory_model
    model = _memory_model
except ImportError:
    model = None

from backend.domain.errors import (
    DomainError,
    LLMError,
    LLMBackendError,
    LLMTimeoutError,
    ToolExecutionError,
    MemoryError,
    TimeoutError,
    SandboxError,
    ValidationError,
    error_to_http_status,
)

__all__ = [
    # Core
    "CodeExecutor",
    "ExecutionConfig",
    "Orchestrator",
    "WSEvent",
    "AgentStep",
    "ErrorCode",
    "ConfigKey",
    "State",
    "StateManager",
    "init_state",
    "save_state",
    "load_state",
    "ReviewResult",
    "CodeReviewer",
    "get_reviewer",
    "review_code",
    "JSONFormatter",
    "LoggerManager",
    "set_correlation_id",
    "get_correlation_id",
    "generate_correlation_id",
    "get_logger",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "log_performance",
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
    "ExecutionRecord",
    "Metrics",
    "MetricsManager",
    "get_metrics_manager",
    "record_execution",
    "get_metrics",
    "get_dashboard_data",
    # Memory
    "MemoryManager",
    "get_memory_manager",
    "add_memory",
    "search_memory",
    "MockLogger",
    "model",
    # Errors
    "DomainError",
    "LLMError",
    "LLMBackendError",
    "LLMTimeoutError",
    "ToolExecutionError",
    "MemoryError",
    "TimeoutError",
    "SandboxError",
    "ValidationError",
    "error_to_http_status",
]