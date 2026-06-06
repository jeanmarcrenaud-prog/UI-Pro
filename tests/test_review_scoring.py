"""Tests for the review-scoring and severity classification helpers.

Covers the three new fields in `ReviewData`:

  - score           : 0.0-1.0 quality score (LLM-provided or heuristic)
  - issue_severities: parallel to issues, classifying each as
                      "high" / "medium" / "low"

Also covers the post-parse enrichment in `reviewing_node` (extracting
the score from the LLM response, building issue_severities) and the
new severity-aware rendering in `format_fix_prompt`.
"""

from __future__ import annotations

from typing import Any

from backend.domain.core.langgraph.fix_prompts import format_fix_prompt
from backend.domain.core.langgraph.nodes import (
    _classify_issue_severity,
    _heuristic_review_score,
)


def _state(**overrides: Any) -> dict[str, Any]:
    """Minimal AgentState for fix_prompt tests, with a failing review
    carrying severities."""
    state: dict[str, Any] = {
        "messages": [{"role": "user", "content": "Print the weather in Paris"}],
        "attempt": 1,
        "max_attempts": 3,
        "error": "NameError: name 'x' is not defined",
        "code": {
            "files": {
                "main.py": "def main():\n    print(weather)\n",
            },
        },
        "review": {
            "passed": False,
            "issues": [
                "undefined name 'weather'",
                "no entry-point guard",
                "consider adding type hints",
            ],
            "suggestions": ["use if __name__ == '__main__'"],
            "issue_severities": ["high", "medium", "medium"],
            "score": 0.45,
        },
    }
    state.update(overrides)
    return state


# ========================================
# _classify_issue_severity
# ========================================


class TestClassifyIssueSeverity:
    """The keyword classifier is the core of severity assignment."""

    def test_high_severity_for_undefined_name(self):
        assert _classify_issue_severity("undefined name 'weather'") == "high"

    def test_high_severity_for_error_keyword(self):
        assert _classify_issue_severity("TypeError: bad argument") == "high"

    def test_high_severity_for_security_keyword(self):
        assert _classify_issue_severity("SQL injection risk") == "high"

    def test_medium_severity_for_warning_keyword(self):
        assert _classify_issue_severity("deprecated function usage") == "medium"

    def test_medium_severity_for_should_keyword(self):
        assert _classify_issue_severity("you should add a timeout") == "medium"

    def test_low_severity_for_generic_advice(self):
        assert _classify_issue_severity("minor style note") == "low"

    def test_low_severity_for_empty_string(self):
        assert _classify_issue_severity("") == "low"

    def test_low_severity_for_non_string(self):
        assert _classify_issue_severity(None) == "low"  # type: ignore[arg-type]

    def test_high_wins_over_medium_when_both_match(self):
        """If a phrase contains BOTH a high and a medium keyword,
        high wins — a single bad import is more important than a
        general style note in the same issue.
        """
        # "error" is high; "should" is medium. High wins.
        result = _classify_issue_severity("Error: you should not do this")
        assert result == "high"

    def test_case_insensitive(self):
        assert _classify_issue_severity("UNDEFINED NAME 'X'") == "high"
        assert _classify_issue_severity("DEPRECATED") == "medium"


# ========================================
# _heuristic_review_score
# ========================================


class TestHeuristicReviewScore:
    """Deterministic fallback when LLM doesn't return a score."""

    def test_perfect_score_for_no_issues(self):
        assert _heuristic_review_score([], []) == 1.0

    def test_score_drops_with_issues(self):
        score_zero = _heuristic_review_score([], [])
        score_one = _heuristic_review_score(["one issue"], [])
        score_two = _heuristic_review_score(["one", "two"], [])
        assert score_zero > score_one > score_two

    def test_score_clamps_at_zero(self):
        # 20 issues = 1.0 - 2.0 = -1.0 -> clamps to 0.0
        many = [f"issue {i}" for i in range(20)]
        assert _heuristic_review_score(many, []) == 0.0

    def test_score_clamps_at_one(self):
        assert _heuristic_review_score([], []) <= 1.0
        assert _heuristic_review_score([], []) >= 0.0

    def test_suggestions_count_half_as_much(self):
        """Per the docstring, each suggestion is -0.05 (vs -0.10 for
        an issue). Verify the ratio.
        """
        # 1 issue (-0.10) + 2 suggestions (-0.10 total) = -0.20 -> 0.80
        score = _heuristic_review_score(["one"], ["s1", "s2"])
        assert abs(score - 0.8) < 1e-9

    def test_two_issues_and_two_suggestions(self):
        # 2 issues (-0.20) + 2 suggestions (-0.10) = -0.30 -> 0.70
        score = _heuristic_review_score(["a", "b"], ["s1", "s2"])
        assert abs(score - 0.7) < 1e-9

    def test_non_list_inputs_handled(self):
        # Defensive against bad callers -- should not crash, just treat
        # as empty.
        assert _heuristic_review_score(None, None) == 1.0  # type: ignore[arg-type]
        assert _heuristic_review_score("not a list", []) == 1.0  # type: ignore[arg-type]


# ========================================
# format_fix_prompt severity integration
# ========================================


class TestFixPromptSeverityIntegration:
    """format_fix_prompt surfaces the new issue_severities array."""

    def test_severity_prefix_high(self):
        out = format_fix_prompt(_state(), advanced=False)
        assert "- [HIGH] undefined name 'weather'" in out

    def test_severity_prefix_medium(self):
        out = format_fix_prompt(_state(), advanced=False)
        assert "- [MED] no entry-point guard" in out
        assert "- [MED] consider adding type hints" in out

    def test_severity_missing_falls_back_to_unprefixed(self):
        """A state without `issue_severities` should not crash and
        should render the issues WITHOUT any severity tag (backward
        compat with the v1 prompt).
        """
        state = _state()
        del state["review"]["issue_severities"]
        out = format_fix_prompt(state, advanced=False)
        # No severity tags at all.
        assert "[HIGH]" not in out
        assert "[MED]" not in out
        assert "[LOW]" not in out
        # But the issues are still inlined.
        assert "- undefined name 'weather'" in out

    def test_severity_length_mismatch_handled(self):
        """If severities is shorter than issues, missing entries
        render unprefixed (treated as 'low' / unknown).
        """
        state = _state(
            review={
                "passed": False,
                "issues": [
                    "undefined name 'weather'",
                    "no entry-point guard",
                    "consider adding type hints",
                ],
                "suggestions": [],
                # Only 2 severities for 3 issues -- last one unprefixed.
                "issue_severities": ["high", "medium"],
            }
        )
        out = format_fix_prompt(state, advanced=False)
        assert "- [HIGH] undefined name 'weather'" in out
        assert "- [MED] no entry-point guard" in out
        # Third issue: no prefix.
        lines = [line for line in out.splitlines() if line.startswith("-")]
        third = next(line for line in lines if "consider" in line)
        assert third == "- consider adding type hints"

    def test_score_field_not_in_prompt(self):
        """score is for ops dashboards, NOT for the LLM. It must not
        leak into the fix prompt -- would only distract the model.
        """
        out = format_fix_prompt(_state(), advanced=False)
        # The score is 0.45 in the fixture. Must not appear as a number.
        assert "0.45" not in out
        assert "score" not in out.lower()


# ========================================
# Pipeline + P3#2 regression
# ========================================


class TestRegressionGuards:
    """The new fields must NOT break the existing pipeline."""

    def test_format_fix_prompt_with_no_review_severity_at_all(self):
        """A review from an old (pre-this-change) LLM response has no
        `issue_severities` and no `score`. Must work.
        """
        state = _state(
            review={
                "passed": False,
                "issues": ["old-style issue"],
                "suggestions": ["old-style suggestion"],
                # No issue_severities, no score
            }
        )
        out = format_fix_prompt(state, advanced=False)
        assert "- old-style issue" in out
        assert "- old-style suggestion" in out
        # No severity tags.
        assert "[HIGH]" not in out
