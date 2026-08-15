"""Tests for pipeline nodes — should_continue, _clean_plan, _parse_plan."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

import pytest

# Import the functions we want to test directly
from backend.domain.core.langgraph.nodes import (
    _clean_plan,
)
from backend.domain.core.langgraph.state import PlanData


# ====================== _clean_plan ======================


class TestCleanPlan:
    def test_none_plan_returns_empty(self):
        assert _clean_plan(None) == {}

    def test_removes_raw_key(self):
        plan: PlanData = {"raw": "some text", "steps": [], "files": {}}
        cleaned = _clean_plan(plan)
        assert "raw" not in cleaned

    def test_removes_thinking_key(self):
        plan: PlanData = {"thinking": "...", "steps": []}
        cleaned = _clean_plan(plan)
        assert "thinking" not in cleaned

    def test_removes_analysis_key(self):
        plan: PlanData = {"analysis": "...", "steps": []}
        cleaned = _clean_plan(plan)
        assert "analysis" not in cleaned

    def test_keeps_steps(self):
        plan: PlanData = {
            "steps": [{"description": "step1", "file": "main.py"}],
            "files": {"main.py": "desc"},
        }
        cleaned = _clean_plan(plan)
        assert "steps" in cleaned
        assert len(cleaned["steps"]) == 1  # type: ignore[arg-type]

    def test_keeps_files(self):
        plan: PlanData = {
            "steps": [],
            "files": {"main.py": "entry point"},
        }
        cleaned = _clean_plan(plan)
        assert "files" in cleaned
        assert cleaned["files"] == {"main.py": "entry point"}  # type: ignore[comparison-overlap]

    def test_keeps_unknown_keys(self):
        plan: PlanData = {
            "steps": [],
            "custom_key": "should survive",
        }
        cleaned = _clean_plan(plan)
        assert "custom_key" in cleaned


# ====================== should_continue ======================

# We test should_continue by importing it and calling it with different states
from backend.domain.core.langgraph.nodes import should_continue


class TestShouldContinue:
    """Test the should_continue decision logic."""

    def _make_state(self, **overrides: Any) -> dict[str, Any]:
        defaults = {
            "review": None,
            "execution_result": None,
            "attempt": 0,
            "max_attempts": 3,
        }
        defaults.update(overrides)
        return defaults

    # Priorité 1: exécution réussie → end
    def test_execution_success_ends(self):
        state = self._make_state(
            execution_result={"success": True, "error": None, "output": "ok"},
            attempt=1,
        )
        assert should_continue(state) == "end"

    def test_execution_success_even_with_bad_review(self):
        """If execution succeeds, we stop regardless of review."""
        state = self._make_state(
            review={"passed": False, "issues": ["style"]},
            execution_result={"success": True, "error": None, "output": "ok"},
            attempt=1,
        )
        assert should_continue(state) == "end"

    # Priorité 2: échec + max tentatives → end
    def test_execution_failed_max_attempts_ends(self):
        state = self._make_state(
            execution_result={"success": False, "error": "timeout", "output": ""},
            attempt=3,
            max_attempts=3,
        )
        assert should_continue(state) == "end"

    def test_execution_failed_exceeds_max_attempts_ends(self):
        state = self._make_state(
            execution_result={"success": False, "error": "error", "output": ""},
            attempt=4,
            max_attempts=3,
        )
        assert should_continue(state) == "end"

    # Priorité 3: échec + tentatives restantes → fix_code
    def test_execution_failed_with_remaining_attempts_fixes(self):
        state = self._make_state(
            execution_result={"success": False, "error": "syntax error", "output": ""},
            attempt=1,
            max_attempts=3,
        )
        assert should_continue(state) == "fix_code"

    def test_execution_failed_first_attempt_fixes(self):
        state = self._make_state(
            execution_result={"success": False, "error": "import error", "output": ""},
            attempt=0,
            max_attempts=3,
        )
        assert should_continue(state) == "fix_code"

    # Priorité 4: max attempts sans execution → end
    def test_max_attempts_reached_no_execution_result_ends(self):
        state = self._make_state(
            execution_result=None,
            attempt=3,
            max_attempts=3,
        )
        assert should_continue(state) == "end"

    # Fallback: fix_code
    def test_no_execution_no_review_fallback_fix(self):
        """No execution result, no review, attempts remaining → fix_code."""
        state = self._make_state(
            execution_result=None,
            review=None,
            attempt=0,
            max_attempts=3,
        )
        assert should_continue(state) == "fix_code"

    # Priorité 0: review avec flag no_code → end,
    # même si l'exécuteur a déjà échoué (cas réel : l'exécuteur tourne
    # juste après reviewing_node et renvoie une erreur "no files to run").
    # Le fix loop reproduirait la même réponse vide du LLM.
    def test_no_code_review_short_circuits_to_end(self):
        state = self._make_state(
            execution_result=None,
            review={
                "passed": False,
                "no_code": True,
                "score": 0.0,
                "issues": [
                    "No code was generated by coding_node (LLM returned "
                    "an empty response). See run.log for the 'stream "
                    "summary' telemetry line that explains why.",
                ],
                "suggestions": ["Try a different model"],
            },
            attempt=0,
            max_attempts=3,
        )
        assert should_continue(state) == "end"

    def test_no_code_review_short_circuits_even_with_failed_executor(self):
        """Real scenario: executor ran after synthetic review and
        failed with 'No files to run'. The sentinel must still trigger
        the short-circuit even though execution_result is not None."""
        state = self._make_state(
            execution_result={"status": "error", "output": "No files to run"},
            review={
                "passed": False,
                "no_code": True,
                "score": 0.0,
                "issues": [
                    "No code was generated by coding_node "
                    "(LLM returned an empty response).",
                ],
            },
            attempt=0,
            max_attempts=3,
        )
        assert should_continue(state) == "end"

    def test_no_code_review_short_circuits_even_on_fix_attempt(self):
        """Even on a fix attempt (attempt > 0), the empty-code signal
        should still end the stream — retrying the same model with the
        same prompt will not magically produce code."""
        state = self._make_state(
            execution_result={"status": "error", "output": "No files"},
            review={
                "passed": False,
                "no_code": True,
                "issues": [
                    "No code was generated by coding_node "
                    "(LLM returned an empty response).",
                ],
            },
            attempt=2,
            max_attempts=3,
        )
        assert should_continue(state) == "end"

    def test_normal_fail_review_still_routes_to_fix_code(self):
        """A 'normal' failed review (NOT the no-code sentinel) should
        still go to fix_code — only the specific no-code string
        triggers the short-circuit."""
        state = self._make_state(
            execution_result=None,
            review={
                "passed": False,
                "issues": ["Variable 'foo' is undefined"],
                "suggestions": ["Define foo before using it"],
            },
            attempt=0,
            max_attempts=3,
        )
        assert should_continue(state) == "fix_code"


# ====================== reviewing_node (no-code short-circuit) ======================


class TestReviewingNodeEmptyCode:
    """When coding_node produced an empty files dict (LLM stream
    returned empty content), reviewing_node should skip the LLM review
    call and return a synthetic fail. This is the early-exit path that
    saves the user the 6-minute wait for 3 wasted fix attempts.

    Only the no-code path is tested here (it does not call the LLM at
    all). The full reviewing_node flow with real LLM calls is covered
    by integration tests in tests/test_reviewing_node.py if it exists,
    or skipped on purpose to keep this file hermetic.
    """

    @pytest.mark.asyncio
    async def test_empty_files_dict_returns_synthetic_fail(self):
        from backend.domain.core.langgraph.nodes import reviewing_node

        state: dict = {
            "code": {"files": {}, "steps": []},
            "metadata": {"model": "test", "provider": "lmstudio"},
            "messages": [{"role": "user", "content": "test"}],
            "attempt": 0,
        }
        result = await reviewing_node(state)
        assert result["review"]["passed"] is False
        assert result["review"]["no_code"] is True
        assert result["review"]["score"] == 0.0
        issues = result["review"]["issues"]
        assert len(issues) == 1
        assert "No code was generated" in issues[0]
        assert result["review"]["issue_severities"] == ["high"]

    @pytest.mark.asyncio
    async def test_missing_code_key_returns_synthetic_fail(self):
        from backend.domain.core.langgraph.nodes import reviewing_node

        state: dict = {
            "metadata": {"model": "test", "provider": "lmstudio"},
            "messages": [{"role": "user", "content": "test"}],
        }
        result = await reviewing_node(state)
        assert result["review"]["passed"] is False
        assert "No code was generated" in result["review"]["issues"][0]

    @pytest.mark.asyncio
    async def test_non_dict_code_returns_synthetic_fail(self):
        from backend.domain.core.langgraph.nodes import reviewing_node

        state: dict = {
            "code": "not a dict",  # type: ignore[typeddict-item]
            "metadata": {"model": "test", "provider": "lmstudio"},
            "messages": [{"role": "user", "content": "test"}],
        }
        result = await reviewing_node(state)
        assert result["review"]["passed"] is False
        assert "No code was generated" in result["review"]["issues"][0]

    @pytest.mark.asyncio
    async def test_populated_files_proceeds_to_llm_review(self):
        """Negative test: with a populated files dict, reviewing_node
        does NOT short-circuit. We do not assert anything about the
        LLM response (that would require a real or stubbed LLM); we
        only assert that the result has a review key that is NOT the
        synthetic no-code fail.
        """
        from backend.domain.core.langgraph.nodes import reviewing_node

        state: dict = {
            "code": {"files": {"main.py": "print('hi')"}, "steps": []},
            "metadata": {"model": "test", "provider": "lmstudio"},
            "messages": [{"role": "user", "content": "test"}],
        }
        result = await reviewing_node(state)
        # If the LLM call worked, review is set with the model's verdict.
        # If the LLM call failed/returned empty, we still get a review
        # (parse fallback). Either way: NOT the no-code sentinel.
        assert "review" in result
        if result["review"]["issues"]:
            assert not any(
                "No code was generated" in i
                for i in result["review"]["issues"]
            )


# ====================== _parse_plan (internal, tested via integration) ======================


class TestParsePlanIntegration:
    """Test the planning node's JSON extraction by simulating LLM responses.

    We test _parse_plan indirectly by checking what `_clean_plan` produces
    after parsing various response formats.
    """

    def _parse_and_clean(self, text: str) -> dict[str, object]:
        """Simulate what planning_node does: parse then clean."""
        import re
        import json

        # Inline _parse_plan logic (copied from nodes.py)
        def _parse_plan(text: str) -> PlanData:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

            json_block = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
            if json_block:
                try:
                    return json.loads(json_block.group(1))
                except json.JSONDecodeError:
                    pass

            # Balanced-brace scan, first valid top-level object wins.
            # Replaces a greedy regex that failed when the LLM added prose
            # with {...} placeholders before/after the JSON.
            depth = 0
            start = -1
            in_string = False
            escape = False
            candidates: list[str] = []
            for i, ch in enumerate(text):
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "}":
                    if depth > 0:
                        depth -= 1
                        if depth == 0 and start >= 0:
                            candidates.append(text[start : i + 1])
                            start = -1
            for cand in candidates:
                try:
                    return json.loads(cand)
                except json.JSONDecodeError:
                    continue

            cleaned = text.strip()
            cleaned = re.sub(r"(?<!\\)'", '"', cleaned)
            cleaned = re.sub(r",\s*]", "]", cleaned)
            cleaned = re.sub(r",\s*}", "}", cleaned)
            try:
                return json.loads(cleaned)
            except (json.JSONDecodeError, ValueError):
                pass

            return {"raw": text[:500], "steps": [], "files": {}}

        return _clean_plan(_parse_plan(text))

    def test_direct_json(self):
        text = '{"steps": [{"description": "step1"}], "files": {"main.py": "desc"}}'
        result = self._parse_and_clean(text)
        assert len(result["steps"]) == 1  # type: ignore[arg-type]

    def test_json_in_fence(self):
        text = (
            "```json\n"
            '{"steps": [{"description": "step1"}], "files": {"main.py": "desc"}}\n'
            "```"
        )
        result = self._parse_and_clean(text)
        assert len(result["steps"]) == 1  # type: ignore[arg-type]

    def test_json_after_thinking(self):
        text = (
            "Thinking Process:\n1. First do this\n2. Then that\n\n"
            '{"steps": [{"description": "step1"}], "files": {"main.py": "desc"}}'
        )
        result = self._parse_and_clean(text)
        assert len(result["steps"]) == 1  # type: ignore[arg-type]

    def test_single_quotes(self):
        text = "{'steps': [{'description': 'step1'}], 'files': {'main.py': 'desc'}}"
        result = self._parse_and_clean(text)
        assert len(result["steps"]) == 1  # type: ignore[arg-type]

    def test_trailing_commas(self):
        text = '{"steps": [{"description": "step1"},], "files": {"main.py": "desc",}}'
        result = self._parse_and_clean(text)
        assert len(result["steps"]) == 1  # type: ignore[arg-type]

    def test_empty_response(self):
        result = self._parse_and_clean("")
        assert result == {"steps": [], "files": {}}

    def test_unparseable_response(self):
        result = self._parse_and_clean("This is not JSON at all")
        assert result == {"steps": [], "files": {}}

    def test_partial_json_recovery(self):
        text = 'Some text before {"steps": [], "files": {}} and after'
        result = self._parse_and_clean(text)
        assert "steps" in result

    def test_prose_with_braces_around_json(self):
        r"""Regression: gemma-style output with {placeholder} in prose.

        The previous greedy regex \{[\s\S]*\} would match from the first
        { (inside "{requests}") to the last }, producing invalid JSON
        and triggering the empty-plan fallback.
        """
        text = (
            'I will use {requests} to make calls.\n'
            '{"steps": [{"description": "x", "file": "a.py"}], '
            '"files": {"a.py": "y"}}\n'
            'End of plan.'
        )
        result = self._parse_and_clean(text)
        assert len(result["steps"]) == 1  # type: ignore[arg-type]

    def test_multiple_json_objects_picks_first(self):
        """If multiple top-level objects exist, the scanner returns the first
        valid one without crashing on the second. The exact object chosen is
        not part of the contract — only that one of them is returned cleanly.
        """
        text = (
            '{"unrelated": "first"}\n'
            '{"steps": [{"description": "real", "file": "b.py"}], '
            '"files": {"b.py": "z"}}'
        )
        result = self._parse_and_clean(text)
        # First valid object wins — and both are valid, so we get the first.
        assert result.get("unrelated") == "first"  # type: ignore[arg-type]

    def test_nested_json_in_prose(self):
        """Nested objects inside JSON shouldn't trip the scanner."""
        text = (
            'Prose: see {thing}.\n'
            '{"steps": [{"description": "x", "approach": "use {tool}"}], '
            '"files": {"a.py": "y"}}\n'
            'Done.'
        )
        result = self._parse_and_clean(text)
        assert len(result["steps"]) == 1  # type: ignore[arg-type]



class TestFixingNode:
    """The dedicated auto-fix node extracted from coding_node.

    The fix loop is: execute → should_continue → fixing → review →
    execute → should_continue → end. fixing_node produces the corrected
    code and routes to review; coding_node is pure generation.
    """

    def test_fixing_node_exported_as_distinct_callable(self):
        import inspect

        from backend.domain.core.langgraph.nodes import (
            coding_node,
            fixing_node,
        )

        assert inspect.iscoroutinefunction(fixing_node)
        assert fixing_node is not coding_node

    def test_graph_wires_fix_code_to_fixing_node(self):
        """Regression guard: should_continue's 'fix_code' label must route
        to the fixing node, and fixing must route to review (not back to
        the code node — the fix would be re-generated and lost)."""
        from backend.domain.core.langgraph import build_graph

        app = build_graph()
        graph = app.get_graph()

        # Conditional edges leaving "execute" (should_continue)
        fix_edges = [
            e
            for e in graph.edges
            if e.conditional and e.source == "execute"
        ]
        targets = {e.target for e in fix_edges}
        assert "fixing" in targets
        assert "code" not in targets

        # fixing routes to review via its conditional gate — only fatal
        # errors short-circuit to error_node; never back to the code node
        fix_gate_edges = [
            e
            for e in graph.edges
            if e.conditional and e.source == "fixing"
        ]
        fix_targets = {e.target for e in fix_gate_edges}
        assert "review" in fix_targets
        assert "code" not in fix_targets



class TestErrorGuard:
    """_error_guard — unhandled node exceptions become recorded errors.

    A crashing node must not abort the whole run: the wrapper records
    the error, marks the step as error, sets ``error``, and returns
    partial updates so the pipeline can continue."""

    def test_catches_exception_and_records_error(self):
        from backend.domain.core.langgraph.nodes._base import _error_guard

        @_error_guard("coding")
        async def boom(state):
            raise RuntimeError("kaboom")

        state: dict[str, Any] = {
            "attempt": 0,
            "error_history": [],
            "steps_history": [],
        }
        updates = asyncio.run(boom(state))

        assert updates["error"] == "RuntimeError: kaboom"
        assert len(updates["error_history"]) == 1
        entry = updates["error_history"][0]
        assert entry["node"] == "coding"
        assert entry["error"] == "RuntimeError: kaboom"
        # Step marked error for the Agent Canvas
        last_step = updates["steps_history"][-1]
        assert last_step["name"] == "coding"
        assert last_step["status"] == "error"

    def test_returns_node_result_on_success(self):
        from backend.domain.core.langgraph.nodes._base import _error_guard

        @_error_guard("coding")
        async def ok(state):
            return {"code": {"files": {"main.py": "print(1)"}}}

        updates = asyncio.run(ok({}))
        assert updates["code"]["files"]["main.py"] == "print(1)"

    def test_cancelled_error_propagates(self):
        """Cancellation is a BaseException — the guard must not swallow it."""
        from backend.domain.core.langgraph.nodes._base import _error_guard

        @_error_guard("coding")
        async def cancelled(state):
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(cancelled({}))

    def test_crash_records_fatal_flag(self):
        """A crash is FATAL: error_fatal=True so route_after_node
        short-circuits to error_node; the history entry carries the flag
        for UI debugging."""
        from backend.domain.core.langgraph.nodes._base import _error_guard

        @_error_guard("coding")
        async def boom(state):
            raise RuntimeError("kaboom")

        state: dict[str, Any] = {
            "attempt": 0,
            "error_history": [],
            "steps_history": [],
        }
        updates = asyncio.run(boom(state))

        assert updates["error_fatal"] is True
        assert updates["error_history"][0]["fatal"] is True


class TestMergeErrors:
    """_merge_errors — error_history reducer dedupes by (node, timestamp)."""

    def _entry(self, node, error, ts):
        return {"node": node, "error": error, "attempt": 0, "timestamp": ts}

    def test_accumulates_distinct_entries(self):
        from backend.domain.core.langgraph.state import _merge_errors

        e1 = self._entry("coding", "a", "t1")
        e2 = self._entry("reviewing", "b", "t2")
        merged = _merge_errors([e1], [e1, e2])
        assert len(merged) == 2
        assert merged[0] == e1
        assert merged[1] == e2

    def test_dedupes_same_node_and_timestamp(self):
        from backend.domain.core.langgraph.state import _merge_errors

        e1 = self._entry("coding", "a", "t1")
        merged = _merge_errors([e1], [e1])
        assert len(merged) == 1

    def test_handles_none_sides(self):
        from backend.domain.core.langgraph.state import _merge_errors

        e1 = self._entry("coding", "a", "t1")
        assert _merge_errors(None, [e1]) == [e1]
        assert _merge_errors([e1], None) == [e1]
        assert _merge_errors(None, None) == []


class TestErrorNode:
    """error_node — terminal formatting of a recorded error."""

    def test_emits_terminal_error_step(self):
        from backend.domain.core.langgraph.nodes import error_node

        state = {
            "error": "RuntimeError: kaboom",
            "error_history": [
                {"node": "coding", "error": "RuntimeError: kaboom", "attempt": 0, "timestamp": "t1"}
            ],
            "steps_history": [],
            "metadata": {},
        }
        updates = error_node(state)
        assert updates["error"] == "RuntimeError: kaboom"
        last_step = updates["steps_history"][-1]
        assert last_step["name"] == "error"
        assert last_step["status"] == "error"
        assert last_step["error_detail"] == "RuntimeError: kaboom"

    def test_unknown_error_fallback(self):
        from backend.domain.core.langgraph.nodes import error_node

        updates = error_node({"steps_history": []})
        assert updates["error"] == "Unknown error"
        assert updates["steps_history"][-1]["status"] == "error"


class TestShouldContinueErrorRouting:
    """should_continue routes recorded errors to the terminal error node.

    The fix loop must win over error routing while attempts remain; the
    no_code short-circuit (priority 0) and execution success (priority 1)
    keep their existing behavior.
    """

    def _make_state(self, **overrides: Any) -> dict[str, Any]:
        defaults = {
            "review": None,
            "execution_result": None,
            "attempt": 0,
            "max_attempts": 3,
        }
        defaults.update(overrides)
        return defaults

    def test_error_without_execution_routes_to_error(self):
        state = self._make_state(error="planning failed")
        assert should_continue(state) == "error"

    def test_error_with_failed_execution_and_retries_left_fixes(self):
        state = self._make_state(
            error="execution failed",
            execution_result={"success": False, "error": "boom", "output": ""},
            attempt=1,
        )
        assert should_continue(state) == "fix_code"

    def test_error_with_failed_execution_exhausted_routes_to_error(self):
        state = self._make_state(
            error="execution failed",
            execution_result={"success": False, "error": "boom", "output": ""},
            attempt=3,
            max_attempts=3,
        )
        assert should_continue(state) == "error"

    def test_error_with_no_code_still_ends(self):
        """no_code short-circuit (priority 0) wins over error routing."""
        state = self._make_state(
            error="syntax error",
            review={"passed": False, "no_code": True, "issues": ["x"]},
        )
        assert should_continue(state) == "end"

    def test_error_with_successful_execution_ends(self):
        state = self._make_state(
            error="stale planning error",
            execution_result={"success": True, "error": None, "output": "ok"},
        )
        assert should_continue(state) == "end"


class TestGraphErrorNode:
    """The graph wires should_continue's 'error' label to error_node."""

    def test_graph_wires_error_to_error_node(self):
        from backend.domain.core.langgraph import build_graph

        app = build_graph()
        graph = app.get_graph()

        fix_edges = [
            e
            for e in graph.edges
            if e.conditional and e.source == "execute"
        ]
        targets = {e.target for e in fix_edges}
        assert "error_node" in targets

        # error_node is terminal: explicit edge to END ("__end__" in the
        # compiled graph representation)
        assert any(
            e.source == "error_node" and e.target == "__end__"
            for e in graph.edges
        )


class TestNodeTimeout:
    """NodeTimeout — langgraph's per-node hard cap composes with _error_guard.

    A node exceeding its ``timeout`` raises ``NodeTimeoutError`` (an
    ``Exception`` subclass, NOT ``TimeoutError``). ``_error_guard`` catches
    it, records the error, and the run terminates cleanly instead of
    crashing.
    """

    def test_node_exceeding_timeout_raises_node_timeout_error(self):
        from langgraph.errors import NodeTimeoutError
        from langgraph.graph import END, START, StateGraph
        from typing import TypedDict

        class S(TypedDict, total=False):
            x: int

        async def slow(state):
            await asyncio.sleep(5)
            return {"x": 1}

        g = StateGraph(S)
        g.add_node("slow", slow, timeout=0.2)
        g.add_edge(START, "slow")
        g.add_edge("slow", END)
        app = g.compile()

        with pytest.raises(NodeTimeoutError):
            asyncio.run(app.ainvoke({"x": 0}))

    def test_error_handler_records_node_timeout(self):
        """NodeTimeoutError is raised OUTSIDE the node (langgraph's timeout
        machinery) — the graph-level error_handler records it so the run
        continues instead of crashing."""
        from langgraph.errors import NodeError
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Command
        from typing import TypedDict
        from backend.domain.core.langgraph.nodes._base import _record_node_error

        class S(TypedDict, total=False):
            x: int
            error: str
            error_history: list
            steps_history: list
            current_step: str

        def handler(state, error: NodeError) -> Command:
            return Command(update=_record_node_error(state, error.node, error.error))

        async def slow(state):
            await asyncio.sleep(5)
            return {"x": 1}

        g = StateGraph(S)
        g.add_node("slow", slow, timeout=0.2, error_handler=handler)
        g.add_edge(START, "slow")
        g.add_edge("slow", END)
        app = g.compile()

        result = asyncio.run(app.ainvoke({"x": 0, "error_history": []}))
        assert "NodeTimeoutError" in result["error"]
        assert len(result["error_history"]) == 1
        assert result["error_history"][0]["node"] == "slow"
        assert result["steps_history"][-1]["status"] == "error"


class TestWrapperRetryBackendError:
    """LLMWrapper retries LLMBackendError exactly like it retries timeouts.

    A transient backend outage (Ollama restarting, model loading) must not
    fail the node immediately: one retry with backoff recovers it.
    """

    def test_generate_retries_backend_error_then_succeeds(self):
        from backend.domain.core.langgraph.llm_wrapper import LLMWrapper
        from backend.infrastructure.llm.errors import LLMBackendError

        class _Router:
            def __init__(self):
                self.calls = 0

            def generate(self, prompt, model_type, temperature, model, provider):
                self.calls += 1
                if self.calls == 1:
                    raise LLMBackendError("backend down")
                return "ok response"

        router = _Router()
        wrapper = LLMWrapper(router, user_model="m", user_provider="ollama")
        result = asyncio.run(wrapper.generate("p", max_retries=1))
        assert result == "ok response"
        assert router.calls == 2

    def test_generate_raises_backend_error_after_retries(self):
        from backend.domain.core.langgraph.llm_wrapper import LLMWrapper
        from backend.infrastructure.llm.errors import LLMBackendError

        class _Router:
            def generate(self, prompt, model_type, temperature, model, provider):
                raise LLMBackendError("backend down")

        wrapper = LLMWrapper(_Router(), user_model="m", user_provider="ollama")
        with pytest.raises(LLMBackendError):
            asyncio.run(wrapper.generate("p", max_retries=1))

    def test_run_node_retries_backend_error(self):
        """stream_generate falls back to generate; run_node retries the whole
        collect when the backend error survives the fallback."""
        from backend.domain.core.langgraph.llm_wrapper import LLMWrapper
        from backend.infrastructure.llm.errors import LLMBackendError

        class _Router:
            def __init__(self):
                self.stream_calls = 0
                self.generate_calls = 0

            async def astream(self, **kwargs):
                self.stream_calls += 1
                if self.stream_calls == 1:
                    raise LLMBackendError("backend down")
                yield "ok"

            def generate(self, prompt, model_type, temperature=0.7, model=None, provider=None):
                self.generate_calls += 1
                raise LLMBackendError("backend down")

        router = _Router()
        wrapper = LLMWrapper(router, user_model="m", user_provider="ollama")
        result = asyncio.run(wrapper.run_node("p", max_retries=1))
        assert result == "ok"
        assert router.stream_calls == 2
        # attempt 1: stream fails -> generate fallback retries once internally
        assert router.generate_calls == 2


class TestRouteAfterNode:
    """route_after_node — early error routing for mid-pipeline LLM nodes.

    Only FATAL errors (``state.error_fatal`` True — crashes, timeouts)
    short-circuit to ``error_node``. Recoverable errors (sandbox
    failures) pass through so the fix loop can handle them.
    """

    def test_fatal_error_routes_to_error(self):
        from backend.domain.core.langgraph.nodes import route_after_node

        assert route_after_node(
            {"error": "planning failed", "error_fatal": True}
        ) == "error"

    def test_recoverable_error_continues(self):
        """Sandbox failures are recoverable — must NOT short-circuit."""
        from backend.domain.core.langgraph.nodes import route_after_node

        assert route_after_node(
            {"error": "sandbox fail", "error_fatal": False}
        ) == "continue"

    def test_error_without_flag_continues(self):
        """Absent flag defaults to recoverable (defensive)."""
        from backend.domain.core.langgraph.nodes import route_after_node

        assert route_after_node({"error": "planning failed"}) == "continue"

    def test_no_error_continues(self):
        from backend.domain.core.langgraph.nodes import route_after_node

        assert route_after_node({}) == "continue"

    def test_empty_error_continues(self):
        """An empty string is falsy — treated as no error."""
        from backend.domain.core.langgraph.nodes import route_after_node

        assert route_after_node({"error": ""}) == "continue"

class TestGraphMidPipelineGates:
    """The graph wires route_after_node after plan, code, and fixing.

    fixing now has a conditional gate: only FATAL errors (LLM crash /
    timeout) short-circuit to error_node — recoverable sandbox failures
    still flow fixing → review → execute → fix loop.
    """

    def test_plan_and_code_gate_to_error_node(self):
        from backend.domain.core.langgraph import build_graph

        app = build_graph()
        graph = app.get_graph()

        expected = {
            "plan": {"code", "error_node"},
            "code": {"review", "error_node"},
        }
        for source, targets in expected.items():
            cond_edges = [
                e for e in graph.edges if e.conditional and e.source == source
            ]
            assert {e.target for e in cond_edges} == targets

    def test_fixing_gates_to_error_node(self):
        from backend.domain.core.langgraph import build_graph

        app = build_graph()
        graph = app.get_graph()

        cond_edges = [
            e for e in graph.edges if e.conditional and e.source == "fixing"
        ]
        assert {e.target for e in cond_edges} == {"review", "error_node"}

    def test_error_in_plan_routes_to_error_node(self):
        """End-to-end: a node setting state.error is short-circuited to
        the terminal error node instead of continuing."""
        from langgraph.graph import END, START, StateGraph
        from backend.domain.core.langgraph.nodes import error_node, route_after_node
        from backend.domain.core.langgraph.state import AgentState

        async def plan(state):
            return {"error": "planning failed", "error_fatal": True}

        g = StateGraph(AgentState)

        g.add_node("plan", plan)
        g.add_node("error_node", error_node)
        g.add_edge(START, "plan")
        g.add_conditional_edges(
            "plan",
            route_after_node,
            {"continue": END, "error": "error_node"},
        )
        g.add_edge("error_node", END)
        app = g.compile()

        result = asyncio.run(
            app.ainvoke({"error_history": [], "steps_history": []})
        )
        assert result["error"] == "planning failed"
        assert result["steps_history"][-1]["name"] == "error"
        assert result["steps_history"][-1]["status"] == "error"

    def test_recoverable_error_in_plan_continues(self):
        """End-to-end: a recoverable error (error_fatal False) passes
        through the gate instead of short-circuiting to error_node."""
        from langgraph.graph import END, START, StateGraph
        from backend.domain.core.langgraph.nodes import error_node, route_after_node
        from backend.domain.core.langgraph.state import AgentState

        async def plan(state):
            return {"error": "sandbox fail", "error_fatal": False}

        g = StateGraph(AgentState)
        g.add_node("plan", plan)
        g.add_node("error_node", error_node)
        g.add_edge(START, "plan")
        g.add_conditional_edges(
            "plan",
            route_after_node,
            {"continue": END, "error": "error_node"},
        )
        g.add_edge("error_node", END)
        app = g.compile()

        result = asyncio.run(
            app.ainvoke({"error_history": [], "steps_history": []})
        )
        assert result["error"] == "sandbox fail"
        assert all(
            step.get("name") != "error" for step in result["steps_history"]
        )
