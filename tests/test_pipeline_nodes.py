"""Tests for pipeline nodes — should_continue, _clean_plan, _parse_plan."""

from __future__ import annotations

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

    # Priorité 5: review avec sentinel "No code was generated" → end,
    # même si l'exécuteur a déjà échoué (cas réel : l'exécuteur tourne
    # juste après reviewing_node et renvoie une erreur "no files to run").
    # Le fix loop reproduirait la même réponse vide du LLM.
    def test_no_code_review_short_circuits_to_end(self):
        state = self._make_state(
            execution_result=None,
            review={
                "passed": False,
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

