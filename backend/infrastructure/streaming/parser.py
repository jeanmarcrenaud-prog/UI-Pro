"""
LangGraph raw event parser — prefix-based dispatch to StreamEvent.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.infrastructure.streaming.models import StreamEvent, StreamStatus

logger = logging.getLogger(__name__)

_PARSERS: dict[str, tuple[str, bool]] = {
    "[STREAM_ID]": ("stream_id", False),
    "[RESUME]": ("resumed", True),
    "[STEP]": ("step", True),
    "[TOKEN]": ("token", False),
    "[TOOL]": ("tool", True),
    "[ERROR]": ("error", True),
    "[AWAITING_APPROVAL]": ("awaiting_approval", False),
    "[EXEC_OUT]": ("exec_output", False),
}


def parse_event(raw_event: str | dict, message_id: str) -> StreamEvent | None:
    """Parse raw event from LangGraph into StreamEvent."""
    if isinstance(raw_event, dict):
        logger.warning(
            "Dict event from stream_agent received (unexpected): %s",
            raw_event.get("type", "?"),
        )
        return None

    if not isinstance(raw_event, str):
        return None

    if raw_event == "[DONE]":
        return StreamEvent(event_type="done", message_id=message_id)

    for prefix, (event_type, has_delim) in _PARSERS.items():
        if not raw_event.startswith(prefix):
            continue

        rest = raw_event[len(prefix) :]
        if has_delim and ":" in rest:
            key, content = rest.split(":", 1)
        else:
            key, content = rest, ""

        if event_type == "stream_id":
            return StreamEvent(
                event_type="stream_id", stream_id=rest, message_id=message_id
            )
        if event_type == "resumed":
            return StreamEvent(
                event_type="resumed", stream_id=key, message_id=message_id
            )
        if event_type == "step":
            return StreamEvent(
                event_type="step",
                step_id=f"step-{key}",
                title=key.replace("_", " ").title(),
                status=StreamStatus.GENERATING,
                content=content,
                message_id=message_id,
            )
        if event_type == "token":
            return StreamEvent(
                event_type="token", content=rest, message_id=message_id
            )
        if event_type == "tool":
            return StreamEvent(
                event_type="tool",
                step_id=f"tool-{key}",
                title=key.replace("_", " ").title(),
                content=content,
                message_id=message_id,
            )
        if event_type == "error":
            return StreamEvent(
                event_type="error",
                content=content,
                code=key,
                message_id=message_id,
            )
        if event_type == "awaiting_approval":
            return StreamEvent(
                event_type="awaiting_approval",
                stream_id=rest,
                content=rest,
                message_id=message_id,
            )
        if event_type == "exec_output":
            return StreamEvent(
                event_type="exec_output",
                content=rest,
                message_id=message_id,
            )

    return None


__all__ = ["parse_event"]
