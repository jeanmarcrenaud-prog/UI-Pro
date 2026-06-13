"""Tests for streaming infrastructure — parser, metrics store, _base helpers.

Covers:
- parse_event with ``||{json}`` metadata suffix
- pipeline_metrics_store rolling window, percentiles, reset
- _base.py: _build_llm, _llm_generate, _llm_run_node, _timed_node token tracking
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# parse_event
# =============================================================================

from backend.infrastructure.streaming.parser import parse_event
from backend.infrastructure.streaming.models import StreamEvent, StreamStatus


class TestParseEvent:
    """parse_event() with various prefixes, especially ``||{json}`` metadata."""

    MESSAGE_ID = "test-msg-001"

    def test_done_prefix(self):
        event = parse_event("[DONE]", self.MESSAGE_ID)
        assert event is not None
        assert event.event_type == "done"

    def test_stream_id_prefix(self):
        event = parse_event("[STREAM_ID]abc123", self.MESSAGE_ID)
        assert event is not None
        assert event.event_type == "stream_id"
        assert event.stream_id == "abc123"

    def test_simple_step_no_metadata(self):
        raw = "[STEP]analyzing:Classifying task as code"
        event = parse_event(raw, self.MESSAGE_ID)
        assert event is not None
        assert event.event_type == "step"
        assert event.step_id == "step-analyzing"
        assert event.content == "Classifying task as code"
        assert event.data == {}

    def test_step_with_json_metadata(self):
        """``||{json}`` suffix should be parsed into event.data."""
        meta = {"duration": 2.34, "tokens": 150, "model_used": "test-model"}
        raw = f"[STEP]coding:Completed||{json.dumps(meta)}"
        event = parse_event(raw, self.MESSAGE_ID)
        assert event is not None
        assert event.event_type == "step"
        assert event.step_id == "step-coding"
        assert event.content == "Completed"
        assert event.data == meta

    def test_step_with_error_metadata(self):
        """Error entries emitted by _record_error."""
        meta = {
            "error": {
                "node": "coding",
                "error": "Syntax error",
                "attempt": 1,
                "timestamp": "2025-01-01T00:00:00",
            }
        }
        raw = f"[STEP]coding:❌ Syntax error||{json.dumps(meta)}"
        event = parse_event(raw, self.MESSAGE_ID)
        assert event is not None
        assert event.data["error"]["node"] == "coding"
        assert event.data["error"]["error"] == "Syntax error"

    def test_step_with_empty_json_metadata(self):
        raw = "[STEP]planning:Created plan||{}"
        event = parse_event(raw, self.MESSAGE_ID)
        assert event is not None
        assert event.data == {}

    def test_step_with_invalid_json_metadata(self):
        """Malformed JSON should be silently ignored — data stays empty."""
        raw = "[STEP]planning:Created plan||{bad json}"
        event = parse_event(raw, self.MESSAGE_ID)
        assert event is not None
        assert event.data == {}

    def test_step_without_content(self):
        """Key only, no colon ⇒ content should be empty."""
        raw = "[STEP]completed"
        event = parse_event(raw, self.MESSAGE_ID)
        assert event is not None
        assert event.event_type == "step"
        assert event.step_id == "step-completed"
        assert event.content == ""

    def test_token_event(self):
        event = parse_event("[TOKEN]def hello():", self.MESSAGE_ID)
        assert event is not None
        assert event.event_type == "token"
        assert event.content == "def hello():"

    def test_tool_event(self):
        event = parse_event("[TOOL]write_file:Created main.py", self.MESSAGE_ID)
        assert event is not None
        assert event.event_type == "tool"
        assert event.step_id == "tool-write_file"
        assert event.content == "Created main.py"

    def test_error_event(self):
        event = parse_event("[ERROR]500:Internal server error", self.MESSAGE_ID)
        assert event is not None
        assert event.event_type == "error"
        assert event.code == "500"
        assert event.content == "Internal server error"

    def test_awaiting_approval(self):
        event = parse_event(
            "[AWAITING_APPROVAL]stream_id:abc-123", self.MESSAGE_ID
        )
        assert event is not None
        assert event.event_type == "awaiting_approval"
        assert "abc-123" in event.content

    def test_exec_output(self):
        event = parse_event("[EXEC_OUT]Hello world", self.MESSAGE_ID)
        assert event is not None
        assert event.event_type == "exec_output"
        assert event.content == "Hello world"

    def test_dict_input_returns_none(self):
        """Dict input is not expected from stream_agent — returns None."""
        event = parse_event({"type": "step"}, self.MESSAGE_ID)
        assert event is None

    def test_none_input_returns_none(self):
        event = parse_event(None, self.MESSAGE_ID)  # type: ignore
        assert event is None

    def test_unknown_prefix_returns_none(self):
        event = parse_event("[UNKNOWN]something", self.MESSAGE_ID)
        assert event is None


# =============================================================================
# pipeline_metrics_store
# =============================================================================

from backend.infrastructure.monitoring.pipeline_metrics_store import (
    _percentile,
    observe_node,
    get_node_metrics,
    get_all_node_metrics,
    reset_node_metrics,
)


class TestPercentile:
    """Linear-interpolated percentile helper."""

    def test_empty_list_returns_zero(self):
        assert _percentile([], 50) == 0.0

    def test_single_element(self):
        assert _percentile([5.0], 50) == 5.0
        assert _percentile([5.0], 99) == 5.0

    def test_median_odd_count(self):
        assert _percentile([1.0, 2.0, 3.0], 50) == 2.0

    def test_median_even_count(self):
        assert _percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5

    def test_p95(self):
        sorted_data = list(range(1, 101))  # 1..100
        p95 = _percentile(sorted_data, 95)
        assert 95.0 <= p95 <= 96.0

    def test_p99(self):
        sorted_data = list(range(1, 101))
        p99 = _percentile(sorted_data, 99)
        assert 99.0 <= p99 <= 100.0


class TestNodeMetricsStore:
    """Rolling window per-node metrics store."""

    def setup_method(self):
        reset_node_metrics()

    def test_empty_node_returns_zero_counts(self):
        metrics = get_node_metrics("nonexistent")
        assert metrics["duration"]["count"] == 0
        assert metrics["tokens"]["count"] == 0

    def test_single_observation(self):
        observe_node("analyzing", 2.5, tokens=150)
        metrics = get_node_metrics("analyzing")
        assert metrics["duration"]["count"] == 1
        assert metrics["duration"]["last"] == 2.5
        assert metrics["duration"]["avg"] == 2.5
        assert metrics["tokens"]["last"] == 150

    def test_multiple_observations(self):
        for i in range(5):
            observe_node("coding", float(i + 1), tokens=(i + 1) * 100)
        metrics = get_node_metrics("coding")
        assert metrics["duration"]["count"] == 5
        assert metrics["duration"]["min"] == 1.0
        assert metrics["duration"]["max"] == 5.0
        assert metrics["tokens"]["total"] == 1500  # 100+200+300+400+500

    def test_percentiles_with_multiple_obs(self):
        for i in range(1, 11):
            observe_node("planning", float(i))
        metrics = get_node_metrics("planning")
        assert metrics["duration"]["count"] == 10
        assert 5.0 <= metrics["duration"]["p50"] <= 6.0
        assert 9.0 <= metrics["duration"]["p95"] <= 10.0

    def test_rolling_window_eviction(self):
        """The store keeps at most 100 observations per node.
        The 101st should evict the oldest (first)."""
        for i in range(101):
            observe_node("analyzing", float(i))
        metrics = get_node_metrics("analyzing")
        assert metrics["duration"]["count"] == 100
        # First value (0.0) was evicted — min should now be 1.0
        assert metrics["duration"]["min"] == 1.0
        assert metrics["duration"]["max"] == 100.0

    def test_reset_clears_all(self):
        observe_node("analyzing", 1.0)
        observe_node("coding", 2.0)
        reset_node_metrics()
        all_metrics = get_all_node_metrics()
        assert all_metrics["nodes"] == {}

    def test_zero_tokens_skipped(self):
        """Zero token count should NOT be recorded (tokens list stays empty)."""
        observe_node("analyzing", 1.0, tokens=0)
        metrics = get_node_metrics("analyzing")
        assert metrics["tokens"]["count"] == 0

    def test_get_all_metrics_returns_all_nodes(self):
        observe_node("a", 1.0)
        observe_node("b", 2.0)
        all_metrics = get_all_node_metrics()
        assert "a" in all_metrics["nodes"]
        assert "b" in all_metrics["nodes"]

    def test_negative_duration_not_filtered(self):
        """Negative duration is unusual but should be stored as-is."""
        observe_node("analyzing", -1.0)
        metrics = get_node_metrics("analyzing")
        assert metrics["duration"]["last"] == -1.0


# =============================================================================
# _base.py helpers — token tracking
# =============================================================================

from backend.domain.core.langgraph.nodes._base import (
    _node_token_counts,
    _get_user_message,
    _get_model_info,
    _clean_plan,
)


class TestGetUserMessage:
    def test_returns_first_user_message(self):
        state: dict[str, Any] = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ]
        }
        assert _get_user_message(state) == "Hello"

    def test_empty_messages_returns_empty(self):
        assert _get_user_message({"messages": []}) == ""

    def test_no_messages_key_returns_empty(self):
        assert _get_user_message({}) == ""

    def test_first_message_not_user_still_returns_it(self):
        """_get_user_message gets messages[0] regardless of role."""
        state: dict[str, Any] = {
            "messages": [{"role": "system", "content": "SYSTEM"}]
        }
        assert _get_user_message(state) == "SYSTEM"


class TestGetModelInfo:
    def test_returns_model_and_provider(self):
        state: dict[str, Any] = {
            "metadata": {"model": "qwen3.5", "provider": "ollama"}
        }
        model, provider = _get_model_info(state)
        assert model == "qwen3.5"
        assert provider == "ollama"

    def test_no_metadata_returns_empty_strings(self):
        model, provider = _get_model_info({})
        assert model == ""
        assert provider == "ollama"


class TestNodeTokenCounts:
    """_node_token_counts module-level dict + _llm_generate/_llm_run_node."""

    def teardown_method(self):
        _node_token_counts.clear()

    @patch("backend.domain.core.langgraph.nodes._base._get_llm_router")
    def test_build_llm_returns_wrapper(self, mock_get_router):
        """_build_llm returns an LLMWrapper with correct model."""
        mock_router = MagicMock()
        mock_get_router.return_value = mock_router

        from backend.domain.core.langgraph.nodes._base import _build_llm

        state: dict[str, Any] = {
            "metadata": {"model": "test-model", "provider": "ollama"},
        }
        llm = _build_llm(state, "fast")
        assert llm is not None
        # Verify router was called
        mock_get_router.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_generate_tracks_token_count(self):
        """_llm_generate should store len(response) in _node_token_counts."""
        _node_token_counts.clear()

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Hello World!"  # 12 chars

        from backend.domain.core.langgraph.nodes._base import _llm_generate

        result = await _llm_generate(mock_llm, "prompt", "analyzing")
        assert result == "Hello World!"
        assert _node_token_counts.get("analyzing") == 12

    @pytest.mark.asyncio
    async def test_llm_run_node_tracks_token_count(self):
        """_llm_run_node should store len(response) in _node_token_counts."""
        _node_token_counts.clear()

        mock_llm = AsyncMock()
        mock_llm.run_node.return_value = "def foo(): pass"  # 15 chars

        from backend.domain.core.langgraph.nodes._base import _llm_run_node

        result = await _llm_run_node(mock_llm, "prompt", "coding")
        assert result == "def foo(): pass"
        assert _node_token_counts.get("coding") == 15

    @pytest.mark.asyncio
    async def test_llm_generate_passes_kwargs(self):
        """Extra kwargs should be forwarded to llm.generate()."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "result"

        from backend.domain.core.langgraph.nodes._base import _llm_generate

        await _llm_generate(mock_llm, "prompt", "test", temperature=0.5, max_tokens=100)
        mock_llm.generate.assert_called_once_with(
            "prompt", temperature=0.5, max_tokens=100
        )


class TestTimedNode:
    """@_timed_node decorator — token tracking, metrics emission."""

    def teardown_method(self):
        _node_token_counts.clear()

    @pytest.mark.asyncio
    async def test_timed_node_resets_token_count(self):
        """@_timed_node should reset token count to 0 before running."""
        _node_token_counts["test_node"] = 999  # Stale value

        from backend.domain.core.langgraph.nodes._base import _timed_node

        mock_fn = AsyncMock()
        mock_fn.__name__ = "mock_node"
        mock_fn.__qualname__ = "mock_node"
        mock_fn.return_value = {"result": "ok"}

        wrapped = _timed_node("test_node")(mock_fn)
        result = await wrapped({"messages": []})

        assert result == {"result": "ok"}
        # Token count was cleared before mock_fn ran
        # (mock_fn doesn't set it, so it stays 0)
        mock_fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_timed_node_pops_token_after(self):
        """@_timed_node should pop token count in finally block."""
        _node_token_counts.clear()

        from backend.domain.core.langgraph.nodes._base import _timed_node

        async def node_with_token(state):
            _node_token_counts["gen_node"] = 42
            return {"done": True}
        node_with_token.__name__ = "node_with_token"
        node_with_token.__qualname__ = "node_with_token"

        wrapped = _timed_node("gen_node")(node_with_token)
        await wrapped({})

        # After the wrapped function completes, the token count should
        # have been popped by _timed_node's finally block
        assert "gen_node" not in _node_token_counts

    @pytest.mark.asyncio
    async def test_timed_node_emits_step_event(self):
        """@_timed_node should call _emit_step with duration and tokens."""
        _node_token_counts.clear()

        from backend.domain.core.langgraph.nodes._base import _timed_node

        async def node_func(state):
            _node_token_counts["emit_node"] = 10
            return {"ok": True}
        node_func.__name__ = "node_func"
        node_func.__qualname__ = "node_func"

        with patch(
            "backend.domain.core.langgraph.nodes._base._emit_step"
        ) as mock_emit:
            wrapped = _timed_node("emit_node")(node_func)
            await wrapped({})

            mock_emit.assert_called_once()
            args, kwargs = mock_emit.call_args
            assert args[0] == "emit_node"  # phase name
            assert args[1] == "completed"
            # data dict should have duration and tokens
            data = kwargs.get("data", args[2] if len(args) > 2 else {})
            assert "duration" in data
            assert data["tokens"] == 10


class TestRecordError:
    """_record_error — appends to error_history AND emits step."""

    def test_appends_to_error_history(self):
        from backend.domain.core.langgraph.nodes._base import _record_error

        state: dict[str, Any] = {"attempt": 0, "error_history": []}
        _record_error(state, "coding", "Syntax error at line 2")

        assert len(state["error_history"]) == 1
        entry = state["error_history"][0]
        assert entry["node"] == "coding"
        assert entry["error"] == "Syntax error at line 2"
        assert entry["attempt"] == 0
        assert "timestamp" in entry

    def test_initializes_empty_history_if_missing(self):
        from backend.domain.core.langgraph.nodes._base import _record_error

        state: dict[str, Any] = {"attempt": 1}
        _record_error(state, "reviewing", "Review failed")
        assert len(state["error_history"]) == 1

    def test_multiple_errors_accumulate(self):
        from backend.domain.core.langgraph.nodes._base import _record_error

        state: dict[str, Any] = {"attempt": 0, "error_history": []}
        _record_error(state, "coding", "Error 1")
        _record_error(state, "coding", "Error 2")
        assert len(state["error_history"]) == 2

    def test_emits_step_event(self):
        """_record_error should call _emit_step to push error to frontend."""
        from backend.domain.core.langgraph.nodes._base import _record_error

        state: dict[str, Any] = {"attempt": 0, "error_history": []}

        with patch(
            "backend.domain.core.langgraph.nodes._base._emit_step"
        ) as mock_emit:
            _record_error(state, "coding", "Syntax error")

            mock_emit.assert_called_once()
            args, kwargs = mock_emit.call_args
            assert args[0] == "coding"
            assert "Syntax error" in args[1]
            data = kwargs.get("data", {})
            assert "error" in data
            assert data["error"]["node"] == "coding"
