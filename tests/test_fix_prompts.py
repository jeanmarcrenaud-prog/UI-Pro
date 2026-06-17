"""Tests for the self-correction prompt helper.

These tests exercise `format_fix_prompt` against fixture states. They
do NOT call the LLM — the helper is pure string assembly. Goal is to
lock the schema-to-template binding so a future refactor of
ReviewData / CodeData doesn't silently break the retry path.
"""

from __future__ import annotations

from typing import Any

from backend.domain.core.langgraph.fix_prompts import (
    ADVANCED_FIX_PROMPT,
    FIX_PROMPT,
    format_fix_prompt,
)


def _state(**overrides: Any) -> dict[str, Any]:
    """Build a minimal AgentState for tests.

    Defaults represent a "previous attempt failed" scenario — most tests
    override at least one field. Keys mirror the AgentState TypedDict.
    """
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
            "issues": ["undefined name 'weather'", "no entry-point guard"],
            "suggestions": ["use if __name__ == '__main__'"],
        },
    }
    state.update(overrides)
    return state


class TestFormatFixPrompt:
    """format_fix_prompt: schema-to-template binding."""

    def test_returns_empty_for_attempt_zero(self):
        """First attempt (attempt == 0) must NOT inject fix context.

        The coding_node appends the result unconditionally; an empty
        string on attempt 0 means the base prompt is used unchanged.
        """
        assert format_fix_prompt(_state(attempt=0)) == ""
        assert format_fix_prompt(_state(attempt=0), advanced=True) == ""

    def test_basic_prompt_contains_execution_error(self):
        """The execution error must appear verbatim in the basic prompt."""
        out = format_fix_prompt(_state(advanced=False))
        assert "NameError: name 'x' is not defined" in out

    def test_basic_prompt_contains_previous_code(self):
        """Previous code (from code.files) must be inlined in the prompt."""
        out = format_fix_prompt(_state(advanced=False))
        # The file content is inlined; the filename header is added by
        # _format_files.
        assert "def main():" in out
        assert "print(weather)" in out
        assert "main.py" in out  # the filename header

    def test_basic_prompt_lists_review_issues(self):
        """Issues (list[str]) must be rendered as bullet lines.

        This is the regression guard for the bug in the user-proposed
        prompt: it called i.get('message') on a list[str], which would
        raise AttributeError. The helper here must NOT crash.
        """
        out = format_fix_prompt(_state(advanced=False))
        assert "- undefined name 'weather'" in out
        assert "- no entry-point guard" in out

    def test_basic_prompt_lists_suggestions(self):
        """Suggestions (list[str]) must be rendered as bullet lines."""
        out = format_fix_prompt(_state(advanced=False))
        assert "- use if __name__ == '__main__'" in out

    def test_basic_prompt_marks_review_failed(self):
        """The review_passed label must reflect the actual state."""
        out_pass = format_fix_prompt(
            _state(review={"passed": True, "issues": [], "suggestions": []}),
            advanced=False,
        )
        out_fail = format_fix_prompt(_state(advanced=False))
        assert "PASSÉ" in out_pass
        assert "À CORRIGER" in out_fail

    def test_missing_review_does_not_crash(self):
        """A retry triggered by execution error alone (review absent)
        must still produce a valid prompt. The review label must
        distinguish "absent" (N/A) from "failed" (À CORRIGER) so the
        LLM doesn't get a misleading signal.
        """
        state = _state()
        del state["review"]
        out = format_fix_prompt(state, advanced=False)
        assert out  # non-empty
        # Review label must reflect "no review", not a failure.
        assert "N/A" in out
        assert "À CORRIGER" not in out
        # Issues/suggestions blocks fall back to "(aucun)" / "(aucune)"
        assert "aucun" in out.lower() or "aucune" in out.lower()

    def test_empty_files_does_not_crash(self):
        """code.files == {} must fall back to a marker, not raise."""
        state = _state(code={"files": {}})
        out = format_fix_prompt(state, advanced=False)
        assert "no previous code available" in out.lower() or "(no previous code" in out

    def test_review_only_no_error_still_triggers_fix(self):
        """The coding_node fix path can also fire from a review failure
        even when no execution error is recorded. The helper must
        accept a state with a failed review and no error.
        """
        state = _state(
            error=None,
            execution_result=None,
            review={
                "passed": False,
                "issues": ["type mismatch"],
                "suggestions": ["add type hints"],
            },
        )
        out = format_fix_prompt(state, advanced=False)
        assert "- type mismatch" in out
        assert "add type hints" in out

    def test_basic_and_advanced_produce_different_output(self):
        """advanced=True must yield the chain-of-thought variant."""
        basic = format_fix_prompt(_state(), advanced=False)
        advanced = format_fix_prompt(_state(), advanced=True)
        assert basic != advanced
        # The advanced variant must reference its three CoT blocks
        # explicitly. We check for the French labels, which is the
        # project's primary prompt language.
        assert "ÉTAPE 1" in advanced
        assert "ÉTAPE 2" in advanced
        assert "ÉTAPE 3" in advanced
        assert "ÉTAPE 4" in advanced
        # And the basic variant must NOT contain them.
        assert "ÉTAPE 1" not in basic

    def test_truncates_long_error(self):
        """A huge error message must be truncated, not crash."""
        huge = "x" * 5000
        out = format_fix_prompt(_state(error=huge), advanced=False)
        assert "truncated" in out.lower()
        # The full error is NOT inlined.
        assert huge not in out

    def test_truncates_long_previous_code(self):
        """A huge code.files entry must be truncated, not crash."""
        big = "x = 1\n" * 5000
        out = format_fix_prompt(
            _state(code={"files": {"main.py": big}}), advanced=False
        )
        assert "truncated" in out.lower()
        # The full file is NOT inlined.
        assert big not in out

    def test_caps_number_of_issues_inlined(self):
        """More than 8 issues → the rest are summarised as "… N more omitted"."""
        many_issues = [f"issue {i}" for i in range(20)]
        state = _state(review={"passed": False, "issues": many_issues, "suggestions": []})
        out = format_fix_prompt(state, advanced=False)
        # First 8 inlined
        assert "- issue 0" in out
        assert "- issue 7" in out
        # The remaining 12 must be summarised
        assert "12 more omitted" in out
        # And the last issue is NOT inlined
        assert "- issue 19" not in out

    def test_caps_number_of_suggestions_inlined(self):
        """Same cap logic for suggestions."""
        many = [f"hint {i}" for i in range(10)]
        state = _state(review={"passed": False, "issues": [], "suggestions": many})
        out = format_fix_prompt(state, advanced=False)
        assert "- hint 0" in out
        assert "- hint 4" in out
        assert "5 more omitted" in out
        assert "- hint 9" not in out

    def test_does_not_call_dict_get_on_string_items(self):
        """Regression guard for the bug in the user-proposed prompt:
        calling .get() on a string issue would raise AttributeError.
        The helper uses str(i) and never treats issues as dicts.
        """
        # If this regresses, the helper will raise AttributeError on
        # this line — that's the failure mode we want to lock out.
        state = _state(
            review={
                "passed": False,
                "issues": [
                    "uses requests (forbidden)",
                    "no timeout on urlopen",
                    "no entry-point guard",
                ],
                "suggestions": ["use urllib"],
            }
        )
        # Should not raise.
        out = format_fix_prompt(state, advanced=False)
        assert "uses requests (forbidden)" in out
        assert "no timeout on urlopen" in out
        assert "no entry-point guard" in out


class TestPromptConstants:
    """Sanity checks on the module-level prompt strings."""

    def test_basic_prompt_format_runs_cleanly(self):
        """The FIX_PROMPT template must be formattable with the full
        field set produced by format_fix_prompt.
        """
        out = format_fix_prompt(_state(), advanced=False)
        # If a placeholder is missing, .format() raises KeyError. This
        # test catches the case where a new placeholder is added to
        # one prompt but not the other.
        assert "KeyError" not in out

    def test_advanced_prompt_format_runs_cleanly(self):
        """Same check for ADVANCED_FIX_PROMPT."""
        out = format_fix_prompt(_state(), advanced=True)
        assert "KeyError" not in out

    def test_prompts_share_format_signature(self):
        """Both templates must accept the same kwargs. If the advanced
        prompt adds a new placeholder the helper must know about it.
        """
        sample_kwargs = {
            "attempt": 1,
            "max_attempts": 3,
            "lang": "python",
            "example_file": "main.py",
            "task_description": "x",
            "previous_code": "x",
            "previous_error": "x",
            "review_passed_label": "À CORRIGER",
            "issues_count": 0,
            "issues_list": "(aucun)",
            "suggestions_list": "(aucune)",
        }
        # Both must format without raising.
        FIX_PROMPT.format(**sample_kwargs)
        ADVANCED_FIX_PROMPT.format(**sample_kwargs)
