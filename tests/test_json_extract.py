"""Tests for robust JSON extraction helpers."""
import sys
import types

# ui_pro_prompts is a local workspace package (packages/prompts) that may
# not be installed in the dev venv. Stub it only if missing so this test
# file stays runnable everywhere; the real module is used when available.
try:
    import ui_pro_prompts  # noqa: F401
except ModuleNotFoundError:
    _stub = types.ModuleType("ui_pro_prompts")
    _stub.CODING_SYSTEM_PROMPT = ""
    sys.modules["ui_pro_prompts"] = _stub

from backend.domain.core.langgraph.nodes._base import _extract_json_object, _strip_thinking


def test_strip_thinking_removes_deepseek_style_block():
    assert _strip_thinking("<thinking>a{b}c</thinking>xyz") == "xyz"


def test_strip_thinking_removes_piped_variant():
    assert _strip_thinking("<|thinking|>zzz<|thinking|>done") == "done"


def test_strip_thinking_leaves_plain_text():
    assert _strip_thinking("no thinking here") == "no thinking here"


def test_thinking_block_with_braces_in_reasoning():
    text = '<thinking>I need to think about {this} carefully</thinking>{"task_type": "code", "summary": "test"}'
    result = _extract_json_object(text)
    assert result == {"task_type": "code", "summary": "test"}


def test_single_quotes_and_trailing_comma():
    text = "{'task_type': 'code', 'summary': 'test',}"
    result = _extract_json_object(text)
    assert result == {"task_type": "code", "summary": "test"}


def test_multiple_objects_picks_correct_one():
    text = 'prefix {bad: 1} {"task_type": "code"} suffix'
    result = _extract_json_object(text)
    assert result == {"task_type": "code"}


def test_no_valid_json_returns_none():
    text = "just some text with no json"
    result = _extract_json_object(text)
    assert result is None


def test_deepseek_style_thinking():
    text = '<thinking>reasoning with {nested} braces</thinking>{"passed": true, "issues": []}'
    result = _extract_json_object(text)
    assert result == {"passed": True, "issues": []}


def test_nested_braces_in_json():
    text = '{"task_type": "code", "plan": {"steps": ["a", "b"]}}'
    result = _extract_json_object(text)
    assert result == {"task_type": "code", "plan": {"steps": ["a", "b"]}}


def test_string_with_brace_inside():
    text = '{"task_type": "code", "summary": "fix {this} bug"}'
    result = _extract_json_object(text)
    assert result == {"task_type": "code", "summary": "fix {this} bug"}
