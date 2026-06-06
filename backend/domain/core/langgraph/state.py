"""State definitions for the LangGraph agent."""

from typing import Any, Literal

from typing_extensions import NotRequired, TypedDict


class Message(TypedDict):
    """A single message in the conversation history."""

    role: Literal["user", "assistant", "system", "tool"]
    content: str
    name: NotRequired[str]


class PlanData(TypedDict, total=False):
    """Implementation plan produced by the planning node."""

    steps: list[dict[str, str]]
    files: dict[str, str]
    approach: str
    raw: str
    thinking: str
    analysis: str


class CodeData(TypedDict, total=False):
    """Code generation output."""

    files: dict[str, str]
    summary: str


class ReviewData(TypedDict, total=False):
    """Code review result.

    `issues` and `suggestions` are the human-readable strings, kept as
    `list[str]` for backward compatibility with the existing parser and
    with `format_fix_prompt`. `issue_severities` (when present) is a
    parallel array where `issue_severities[i]` classifies `issues[i]`
    as one of "high" / "medium" / "low". `score` is a 0.0-1.0 quality
    score, useful for ops dashboards and for prioritising retry context.
    All three new fields are optional: existing producers and consumers
    that don't know about them keep working unchanged.
    """

    passed: bool
    issues: list[str]
    suggestions: list[str]
    raw: str
    score: float
    issue_severities: list[str]


class ExecutionResult(TypedDict, total=False):
    """Sandbox execution outcome."""

    success: bool
    output: str
    error: str
    files_written: list[str]
    duration_ms: float


class Metadata(TypedDict, total=False):
    """Session metadata."""

    start_time: str
    model: str
    provider: str
    stream_id: str


class AgentState(TypedDict, total=False):
    """Persistent state for the LangGraph agent pipeline.

    Used by both langgraph/ and orchestrator_async.py pipelines.
    All fields are optional (total=False) to allow partial updates
    at each graph node step.
    """

    messages: list[Message]
    task_type: str | None  # Classification result from analyzing_node
    plan: PlanData | None
    code: CodeData | None
    review: ReviewData | None
    execution_result: ExecutionResult | None
    error: str | None
    attempt: int
    max_attempts: int
    session_id: str
    metadata: Metadata
    # Streaming checkpoint fields
    stream_id: str | None
    last_token_index: int
    checkpoint_enabled: bool
