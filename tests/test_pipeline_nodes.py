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

            brace_match = re.search(r"\{[\s\S]*\}", text)
            if brace_match:
                try:
                    return json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass

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
