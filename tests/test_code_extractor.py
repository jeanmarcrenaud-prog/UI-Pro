"""Tests for code_extractor — markdown code block extraction with filenames."""

from __future__ import annotations

import pytest

from backend.domain.core.langgraph.code_extractor import extract_code_dict
from backend.domain.core.langgraph.code_extractor.extractor import (
    _extract_filename_from_header,
    _strategy_python_blocks,
)


# ====================== Filename from header ======================


class TestExtractFilenameFromHeader:
    def test_double_hash_header(self):
        text = "## main.py\n```python\nprint('hello')\n```"
        pos = text.find("```python")
        assert _extract_filename_from_header(text, pos) == "main.py"

    def test_filename_comment(self):
        text = "# filename: app.py\n```python\nprint('hi')\n```"
        pos = text.find("```python")
        assert _extract_filename_from_header(text, pos) == "app.py"

    def test_with_path(self):
        text = "## subdir/util.py\n```python\nprint('hi')\n```"
        pos = text.find("```python")
        assert _extract_filename_from_header(text, pos) == "subdir/util.py"

    def test_no_header(self):
        text = "```python\nprint('hi')\n```"
        pos = text.find("```python")
        assert _extract_filename_from_header(text, pos) is None

    def test_with_intervening_text(self):
        text = "## main.py\nsome random text\n```python\nprint('hi')\n```"
        pos = text.find("```python")
        # The random text is before the block, so it should still find the ## header
        # Actually, the function searches backward to the nearest non-empty line
        # The nearest non-empty line before ```python is "some random text" which doesn't match
        assert _extract_filename_from_header(text, pos) is None

    def test_only_hash_header_without_double(self):
        text = "# main.py\n```python\nprint('hi')\n```"
        pos = text.find("```python")
        # Single # is not a valid header pattern (must be ##)
        assert _extract_filename_from_header(text, pos) is None


# ====================== Strategy 1: Python blocks ======================


class TestStrategyPythonBlocks:
    def test_single_file_with_header(self):
        text = "## main.py\n```python\nprint('hello world')\n```"
        result = _strategy_python_blocks(text)
        assert result is not None
        assert "main.py" in result["files"]
        assert "hello world" in result["files"]["main.py"]

    def test_multi_file_with_headers(self):
        text = (
            "## main.py\n```python\nimport requests\nprint('ok')\n```\n\n"
            "## utils.py\n```python\ndef helper():\n    return 42\n```"
        )
        result = _strategy_python_blocks(text)
        assert result is not None
        assert "main.py" in result["files"]
        assert "utils.py" in result["files"]
        assert "import requests" in result["files"]["main.py"]
        assert "return 42" in result["files"]["utils.py"]

    def test_no_python_blocks(self):
        text = "Just some text without code blocks"
        assert _strategy_python_blocks(text) is None

    def test_empty_block(self):
        text = "## empty.py\n```python\n```"
        result = _strategy_python_blocks(text)
        assert result is None or len(result["files"]) == 0

    def test_filename_dedup(self):
        text = (
            "## same.py\n```python\nx = 1\n```\n"
            "## same.py\n```python\ny = 2\n```"
        )
        result = _strategy_python_blocks(text)
        assert result is not None
        assert len(result["files"]) == 2
        names = list(result["files"].keys())
        assert names[0] == "same.py"
        assert names[1] != names[0]  # deduplicated

    def test_with_indentation(self):
        text = "## app.py\n```python\n    def foo():\n        pass\n```"
        result = _strategy_python_blocks(text)
        assert result is not None
        content = result["files"]["app.py"]
        assert "def foo():" in content
        assert content.strip().startswith("def")  # dedented


# ====================== Full extract_code_dict ======================


class TestExtractCodeDict:
    def test_markdown_python_blocks(self):
        response = (
            "## main.py\n"
            "```python\n"
            "print('hello')\n"
            "```"
        )
        result = extract_code_dict(response)
        assert "files" in result
        assert "main.py" in result["files"]

    def test_multi_file_markdown(self):
        response = (
            "## main.py\n"
            "```python\n"
            "import requests\n"
            "print('fetching')\n"
            "```\n\n"
            "## utils.py\n"
            "```python\n"
            "def helper():\n"
            "    pass\n"
            "```"
        )
        result = extract_code_dict(response)
        assert len(result["files"]) == 2
        assert "main.py" in result["files"]
        assert "utils.py" in result["files"]

    def test_legacy_json_format(self):
        response = '{"files": {"script.py": "print(\'legacy\')\\n"}}'
        result = extract_code_dict(response)
        assert "script.py" in result["files"]

    def test_legacy_json_with_files_key(self):
        response = (
            '{\n'
            '  "files": {\n'
            '    "app.py": "import os\\nprint(os.getcwd())\\n"\n'
            '  }\n'
            '}'
        )
        result = extract_code_dict(response)
        assert "app.py" in result["files"]

    def test_json_in_code_fence(self):
        response = (
            "```json\n"
            '{"files": {"script.py": "print(\'in fence\')\\n"}}\n'
            "```"
        )
        result = extract_code_dict(response)
        assert "script.py" in result["files"]

    def test_mixed_format_prefers_python_blocks(self):
        """Strategy 1 (python blocks) should take priority over JSON."""
        response = (
            "## main.py\n"
            "```python\n"
            "print('from block')\n"
            "```\n\n"
            '{"files": {"ignored.py": "print(\'from json\')\\n"}}'
        )
        result = extract_code_dict(response)
        # Should find the python block first
        assert "main.py" in result["files"]

    def test_preamble_stripping(self):
        response = (
            "Here's the code you requested:\n\n"
            "## main.py\n"
            "```python\n"
            "print('hello')\n"
            "```"
        )
        result = extract_code_dict(response)
        assert "main.py" in result["files"]

    def test_empty_response(self):
        result = extract_code_dict("")
        # Empty LLM response (e.g. timeout) yields empty files dict
        # with explicit 'steps' key, so downstream code can distinguish
        # "nothing to execute" from "fallback raw text".
        assert "files" in result
        assert result["files"] == {}
        assert result.get("steps") == []

    def test_whitespace_only_response(self):
        result = extract_code_dict("   \n\n  \n")
        assert "files" in result
        assert result["files"] == {}

    def test_no_code_blocks(self):
        result = extract_code_dict("Just some text")
        assert "files" in result
        assert "main.py" in result["files"]  # fallback

    def test_unterminated_code_fence(self):
        response = (
            "## main.py\n"
            "```python\n"
            "print('hello')\n"
            # missing closing ```
        )
        result = extract_code_dict(response)
        assert "files" in result
        # Should fall through strategies and eventually fallback

    def test_code_with_syntax_errors_is_salvaged(self):
        response = "## main.py\n```python\nprint('unterminated\n```"
        result = extract_code_dict(response)
        assert "files" in result
        # Even with syntax error, the file should survive via fallback
        assert "main.py" in result["files"]


# ====================== Edge cases ======================


class TestExtractEdgeCases:
    def test_file_with_dashes_in_name(self):
        response = "## my-script.py\n```python\nx = 1\n```"
        result = extract_code_dict(response)
        assert "my-script.py" in result["files"]

    def test_file_with_underscores(self):
        response = "## my_script.py\n```python\nx = 1\n```"
        result = extract_code_dict(response)
        assert "my_script.py" in result["files"]

    def test_multiple_python_versions(self):
        response = (
            "```python\nprint('v1')\n```\n"
            "```python\nprint('v2')\n```"
        )
        result = extract_code_dict(response)
        # Without ## headers, falls back to file_1.py, file_2.py
        assert len(result["files"]) >= 1

    def test_py_typed_in_python_block(self):
        """PEP 561 marker accepted now .typed extension is whitelisted.

        LLM generates py.typed inside a ```python block following the
        same ## filename convention as .py files.
        """
        response = (
            "## src/mytool/__init__.py\n"
            "```python\n"
            "from .core import MyTool\n"
            "```\n\n"
            "## src/mytool/py.typed\n"
            "```python\n"
            "# Marker for PEP 561 typed package support\n"
            "```\n"
        )
        result = extract_code_dict(response)
        assert "src/mytool/__init__.py" in result["files"]
        assert "src/mytool/py.typed" in result["files"]

    def test_py_typed_survives_salvage_with_other_files(self):
        """When py.typed is included alongside real .py files, all survive."""
        response = (
            "## main.py\n"
            "```python\n"
            "def hello():\n"
            "    print('hi')\n"
            "```\n\n"
            "## py.typed\n"
            "```python\n"
            "# Marker for PEP 561\n"
            "```\n"
        )
        result = extract_code_dict(response)
        assert "main.py" in result["files"]
        assert "py.typed" in result["files"]
