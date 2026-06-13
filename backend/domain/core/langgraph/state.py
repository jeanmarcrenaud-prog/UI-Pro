"""State definitions for the LangGraph agent."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from typing_extensions import NotRequired, TypedDict


# ── LangGraph reducers ───────────────────────────────────────────────


def _merge_messages(
    a: list[Any] | None, b: list[Any] | None
) -> list[Any]:
    """Concatenate message lists.  Like ``add_messages`` but preserves
    plain-dict messages (does NOT convert to ``BaseMessage``)."""
    if not b:
        return a or []
    if not a:
        return b
    return a + b


def _last_wins(a: Any, b: Any) -> Any:
    """Simple "last value wins" reducer — equivalent to LangGraph's
    default shallow merge but explicitly declared so the schema is
    self-documenting."""
    return b if b is not None else a


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


class StepInfo(TypedDict, total=False):
    """Tracking info for a single pipeline step, persisted in the state
    so the frontend Agent Canvas can hydrate from checkpoints on resume."""

    name: str
    status: Literal["pending", "running", "done", "error"]
    model_used: str | None
    tokens: int
    duration_ms: int
    started_at: str | None  # ISO-8601


def _merge_steps(
    left: list[StepInfo], right: list[StepInfo]
) -> list[StepInfo]:
    """Merge steps history — last version of each step wins by name.

    Unlike ``_last_wins`` (which replaces the whole list), this reducer
    merges step-by-step so that two nodes updating different step names
    don't erase each other's changes."""
    merged = {s["name"]: s for s in left}
    for step in right:
        merged[step["name"]] = step
    return list(merged.values())


class AgentState(TypedDict, total=False):
    """Persistent state for the LangGraph agent pipeline.

    Used by both langgraph/ and orchestrator_async.py pipelines.
    All fields are optional (total=False) to allow partial updates
    at each graph node step.

    Fields annotated with ``Annotated[_, reducer]`` use LangGraph
    reducers — see the individual reducer functions for semantics.
    """

    messages: Annotated[list[Message], _merge_messages]
    task_type: Annotated[str | None, _last_wins]
    plan: Annotated[PlanData | None, _last_wins]
    code: Annotated[CodeData | None, _last_wins]
    review: Annotated[ReviewData | None, _last_wins]
    execution_result: Annotated[ExecutionResult | None, _last_wins]
    error: Annotated[str | None, _last_wins]
    attempt: Annotated[int, _last_wins]
    max_attempts: Annotated[int, _last_wins]
    session_id: Annotated[str, _last_wins]
    metadata: Annotated[Metadata, _last_wins]
    # Human-in-the-loop approval (execute / correct / cancel)
    approval_status: Literal["PENDING", "APPROVED", "REJECTED", None]
    approval_reason: str | None

    # Language detected from user request (e.g. "python", "powershell", "bash")
    language: str | None

    # Streaming checkpoint fields
    stream_id: Annotated[str | None, _last_wins]
    last_token_index: Annotated[int, _last_wins]
    checkpoint_enabled: Annotated[bool, _last_wins]

    # Step tracking for Agent Canvas (populated by @_timed_node helpers)
    current_step: Annotated[str, _last_wins]
    steps_history: Annotated[list[StepInfo], _merge_steps]
    files_generated: Annotated[dict[str, str], _last_wins]
    thinking_mode: Annotated[bool, _last_wins]

    # Error history — each entry: {"node": str, "error": str, "attempt": int, "timestamp": str}
    error_history: Annotated[list[dict[str, object]], _last_wins]
