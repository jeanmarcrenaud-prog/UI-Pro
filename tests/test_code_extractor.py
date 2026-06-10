"""Tests for code_extractor — markdown code block extraction with filenames."""

from __future__ import annotations

import pytest

from backend.domain.core.langgraph.code_extractor import extract_code_dict
from backend.domain.core.langgraph.code_extractor.extractor import (
    _dedup_filename,
    _extract_filename_from_header,
    _normalize_block_indent,
    _strategy_python_blocks,
    _validate_block,
)
from backend.domain.core.langgraph.code_extractor.repair import (
    fix_indentation,
    fix_syntax_errors,
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


# ====================== _normalize_block_indent ======================


class TestNormalizeBlockIndent:
    def test_empty_string(self):
        assert _normalize_block_indent("") == ""

    def test_whitespace_only(self):
        assert _normalize_block_indent("   \n\n   \n") == ""

    def test_no_indent_unchanged(self):
        block = "print('hi')\nx = 1"
        assert _normalize_block_indent(block) == block

    def test_uniform_indent_dedented(self):
        block = "    print('hi')\n    x = 1"
        result = _normalize_block_indent(block)
        assert result == "print('hi')\nx = 1"

    def test_mixed_indent_dedents_to_min(self):
        block = "        if True:\n            print('hi')\n        x = 1"
        result = _normalize_block_indent(block)
        # The minimum non-empty indent is 8, so all lines are dedented by 8
        assert result == "if True:\n    print('hi')\nx = 1"

    def test_tabs_expanded_to_spaces(self):
        # Tab at start counts as 4 spaces of indent
        block = "\tprint('hi')\n\tx = 1"
        result = _normalize_block_indent(block)
        # expandtabs(4) makes both lines have 4 leading spaces
        # min_indent=4, so dedented to 0
        assert result == "print('hi')\nx = 1"

    def test_preserves_empty_lines_as_empty(self):
        block = "    print('hi')\n\n    x = 1"
        result = _normalize_block_indent(block)
        # Empty line stays empty (not dropped, not dedented)
        assert "print('hi')" in result
        assert "x = 1" in result
        # The blank line between should still be present
        assert "\n\n" in result or result.count("\n") == 2


# ====================== _dedup_filename ======================


class TestDedupFilename:
    def test_first_occurrence_unchanged(self):
        seen: dict[str, int] = {}
        assert _dedup_filename("main.py", seen) == "main.py"
        assert seen == {"main.py": 1}

    def test_second_occurrence_appends_counter(self):
        seen: dict[str, int] = {}
        _dedup_filename("main.py", seen)
        assert _dedup_filename("main.py", seen) == "main_2.py"
        assert seen == {"main.py": 2}

    def test_third_occurrence(self):
        seen: dict[str, int] = {}
        _dedup_filename("main.py", seen)
        _dedup_filename("main.py", seen)
        assert _dedup_filename("main.py", seen) == "main_3.py"
        assert seen == {"main.py": 3}

    def test_no_extension_filename(self):
        seen: dict[str, int] = {}
        _dedup_filename("Makefile", seen)
        assert _dedup_filename("Makefile", seen) == "Makefile_2"
        assert seen == {"Makefile": 2}

    def test_different_names_have_independent_counters(self):
        seen: dict[str, int] = {}
        assert _dedup_filename("a.py", seen) == "a.py"
        assert _dedup_filename("b.py", seen) == "b.py"
        # Reusing `a.py` should still only see one prior occurrence
        assert _dedup_filename("a.py", seen) == "a_2.py"
        # `b.py` counter is independent
        assert seen == {"a.py": 2, "b.py": 1}

    def test_multi_dot_filename(self):
        # `my.script.py` — the last dot determines the extension
        seen: dict[str, int] = {}
        _dedup_filename("my.script.py", seen)
        assert _dedup_filename("my.script.py", seen) == "my.script_2.py"


# ====================== _validate_block ======================


class TestValidateBlock:
    """Tests pour la validation unifiée des blocs (Python et génériques)."""

    # ── Mode strict=True (ex-Stratégie 1 : blocs ```python) ──────────

    def test_strict_valid_python_returned_unchanged(self):
        content = "def hello():\n    print('hi')\n"
        result = _validate_block("test.py", content, strict=True)
        assert "def hello" in result
        assert "print" in result

    def test_strict_over_indented_salvaged(self):
        content = "        def hello():\n            print('hi')\n"
        result = _validate_block("test.py", content, strict=True)
        assert "def hello" in result

    def test_strict_completely_broken_returns_non_empty(self):
        content = "((( this is not python @@@ !!!"
        result = _validate_block("test.py", content, strict=True)
        assert isinstance(result, str)
        assert result

    def test_strict_empty_content(self):
        result = _validate_block("test.py", "", strict=True)
        assert result == ""

    # ── Mode normal (ex-Stratégie 2 : blocs génériques) ─────────────

    def test_normal_json_block_returned(self):
        content = '{"key": "value"}'
        result = _validate_block("data.json", content)
        assert result == content

    def test_normal_shell_script_returned(self):
        content = "#!/bin/bash\necho hello"
        result = _validate_block("script.sh", content)
        assert result == content

    def test_normal_invalid_extension_warns_and_keeps_content(self, caplog):
        content = "some content here"
        with caplog.at_level("WARNING"):
            result = _validate_block("test.foo", content)
        assert result == content
        assert any("test.foo" in rec.message for rec in caplog.records)

    def test_normal_unsafe_chars_warns_and_keeps_content(self, caplog):
        content = "x = 1"
        with caplog.at_level("WARNING"):
            result = _validate_block("test\x00.py", content)
        assert result == content
        assert any("test" in rec.message for rec in caplog.records)


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


# ====================== fix_syntax_errors ======================


class TestFixSyntaxErrors:
    """Cas limites pour la réparation syntaxique (tokenize + fallback)."""

    def test_bracket_inside_string_untouched(self):
        """Un ) dans une string ne doit pas être supprimé."""
        code = 'print("hello ) world")'
        assert fix_syntax_errors(code) == code
        assert compile(code, "<test>", "exec")

    def test_fstring_with_braces(self):
        """Les {} des f-strings ne doivent pas fausser le matching."""
        code = 'print(f"count = {count}")'
        assert fix_syntax_errors(code) == code
        assert compile(code, "<test>", "exec")

    def test_comment_with_delimiters(self):
        """Les délimiteurs dans un commentaire doivent être ignorés."""
        code = "x = 1  # ) } ]"
        assert fix_syntax_errors(code) == code
        assert compile(code, "<test>", "exec")

    def test_triple_quotes_with_nested_delimiters(self):
        """Triple quotes avec délimiteurs imbriqués."""
        code = '"""\n)\n}\n]\n"""'
        assert fix_syntax_errors(code) == code
        assert compile(code, "<test>", "exec")

    def test_missing_bracket_appended(self):
        """Un crochet manquant doit être ajouté."""
        code = "x = [1, 2"
        result = fix_syntax_errors(code)
        assert result != code
        assert compile(result, "<test>", "exec")

    def test_extra_bracket_removed_in_fallback(self):
        """Un crochet en trop (fallback caractère)."""
        code = "x = [1, 2]]"
        result = fix_syntax_errors(code)
        assert compile(result, "<test>", "exec")

    def test_bracket_in_string_with_missing_closer(self):
        """Bracket dans une string + bracket manquant = réparé sans casser la string."""
        code = "x = [1, 2,\nprint(')')"
        result = fix_syntax_errors(code)
        assert compile(result, "<test>", "exec")

    def test_nested_missing_brackets(self):
        """Plusieurs niveaux de brackets manquants."""
        code = "x = [1, (2"
        result = fix_syntax_errors(code)
        assert compile(result, "<test>", "exec")

    def test_already_valid_unchanged(self):
        """Code déjà valide retourné inchangé."""
        code = "def foo():\n    pass"
        assert fix_syntax_errors(code) == code
        assert compile(code, "<test>", "exec")

    def test_empty_and_whitespace(self):
        """Entrées vides."""
        assert fix_syntax_errors("") == ""
        assert fix_syntax_errors("   ") == "   "


# ====================== fix_indentation ======================


class TestFixIndentation:
    """Cas limites pour la normalisation d'indentation."""

    def test_tabs_expanded(self):
        """Les tabulations sont converties en espaces."""
        code = "\tdef foo():\n\t\tpass"
        result = fix_indentation(code)
        assert compile(result, "<test>", "exec")
        assert "\t" not in result

    def test_mixed_tabs_spaces(self):
        """Mélange tabs + espaces normalisé."""
        code = "\tdef foo():\n\t    pass"
        result = fix_indentation(code)
        assert compile(result, "<test>", "exec")
        assert "\t" not in result

    def test_already_valid(self):
        """Code déjà bien indenté."""
        code = "def foo():\n    pass"
        assert fix_indentation(code) == code

    def test_single_line_unchanged(self):
        """Une seule ligne → inchangé."""
        code = "    pass"
        assert fix_indentation(code) == code

    def test_no_indent_needed(self):
        """Code sans indentation."""
        code = "import os\nimport sys"
        assert fix_indentation(code) == code
