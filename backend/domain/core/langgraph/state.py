"""State definitions for the LangGraph agent."""

from typing import Any, Optional

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    messages: list[dict[str, Any]]
    plan: Optional[dict[str, Any]]
    code: Optional[dict[str, Any]]
    review: Optional[dict[str, Any]]
    execution_result: Optional[dict[str, Any]]
    error: Optional[str]
    attempt: int
    max_attempts: int
    session_id: str
    metadata: dict[str, Any]
    # Streaming checkpoint fields
    stream_id: Optional[str]
    last_token_index: int
    checkpoint_enabled: bool