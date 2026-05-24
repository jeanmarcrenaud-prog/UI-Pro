"""State definitions for the LangGraph agent."""

from typing import Any

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    messages: list[dict[str, Any]]
    plan: dict[str, Any] | None
    code: dict[str, Any] | None
    review: dict[str, Any] | None
    execution_result: dict[str, Any] | None
    error: str | None
    attempt: int
    max_attempts: int
    session_id: str
    metadata: dict[str, Any]
    # Streaming checkpoint fields
    stream_id: str | None
    last_token_index: int
    checkpoint_enabled: bool
