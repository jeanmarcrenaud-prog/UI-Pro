"""Multi-strategy extraction of code dicts from raw LLM output."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from typing import Any

from .models import ExtractedCode, ExtractedFile, _PYTHON_EXTENSIONS
from .repair import fix_indentation, fix_syntax_errors

logger = logging.getLogger(__name__)

# Language → file extension mapping for generic code blocks (Strategy 6)
LANG_EXTENSIONS: dict[str, str] = {
    "powershell": ".ps1",
    "ps1": ".ps1",
    "posh": ".ps1",
    "bash": ".sh",
    "sh": ".sh",
    "shell": ".sh",
    "zsh": ".sh",
    "javascript": ".js",
    "js": ".js",
    "node": ".js",
    "typescript": ".ts",
    "ts": ".ts",
    "jsx": ".jsx",
    "tsx": ".tsx",
    "html": ".html",
    "htm": ".html",
    "css": ".css",
    "scss": ".scss",
    "less": ".less",
    "yaml": ".yaml",
    "yml": ".yaml",
    "toml": ".toml",
    "ini": ".ini",
    "cfg": ".ini",
    "conf": ".conf",
    "dockerfile": "Dockerfile",
    "docker": "Dockerfile",
    "sql": ".sql",
    "rust": ".rs",
    "rs": ".rs",
    "go": ".go",
    "golang": ".go",
    "java": ".java",
    "c": ".c",
    "cpp": ".cpp",
    "c++": ".cpp",
    "cxx": ".cpp",
    "h": ".h",
    "hpp": ".hpp",
    "ruby": ".rb",
    "rb": ".rb",
    "php": ".php",
    "swift": ".swift",
    "kotlin": ".kt",
    "kt": ".kt",
    "scala": ".scala",
    "r": ".r",
    "R": ".r",
    "lua": ".lua",
    "pl": ".pl",
    "pm": ".pm",
    "perl": ".pl",
    "cs": ".cs",
    "csharp": ".cs",
    "fs": ".fs",
    "fsharp": ".fs",
    "zig": ".zig",
    "nim": ".nim",
    "elixir": ".ex",
    "ex": ".ex",
    "exs": ".exs",
    "erlang": ".erl",
    "erl": ".erl",
    "haskell": ".hs",
    "hs": ".hs",
    "clojure": ".clj",
    "clj": ".clj",
    "cljs": ".cljs",
    "makefile": "Makefile",
    "make": "Makefile",
    "batch": ".bat",
    "bat": ".bat",
    "cmd": ".cmd",
    "diff": ".diff",
    "patch": ".patch",
    "xml": ".xml",
    "svg": ".svg",
    "text": ".txt",
    "plain": ".txt",
    "markdown": ".md",
    "md": ".md",
    "env": ".env",
    "json": ".json",
    "jsonc": ".jsonc",
}

# Common LLM preamble phrases to ignore at the start of a response.
# Includes both English ("Thinking", "Here's") and French ("Voici", "Je vais",
# "Analyse") markers since the LLM may produce either.
_LLM_PREAMBLE_PATTERNS = re.compile(
    r"^(#|//|-\s*)?(Thinking|Analyzing|Reasoning|Here'?s|Here is|Let me|I'?ll|The (solution|code|approach|best)|Code[:\s]|Voici|Je vais|Analyse)",
    re.IGNORECASE,
)


def _strip_llm_preamble(text: str) -> str:
    """Strip the LLM 'thinking process' or 'here's the code' preamble from a response."""
    lines = text.split("\n")
    code_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if _LLM_PREAMBLE_PATTERNS.match(stripped):
            code_start = i + 1
        elif stripped.startswith(("```", "{", "import ", "from ", "def ", "class ", "print")):
            break
        else:
            code_start = i
            break
    trimmed = "\n".join(lines[code_start:]).strip()
    return trimmed if trimmed else text


def _find_json_objects(text: str) -> list[str]:
    """Find top-level JSON objects via brace counting (respects string literals)."""
    objects: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            depth = 1
            start = i
            i += 1
            while i < len(text) and depth > 0:
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                if text[i] in ("'", '"'):
                    quote = text[i]
                    i += 1
                    while i < len(text) and text[i] != quote:
                        if text[i] == "\\":
                            i += 1
                        i += 1
                i += 1
            if depth == 0:
                objects.append(text[start:i])
        else:
            i += 1
    return objects


# ---------------------------------------------------------------------------
# Block-processing helpers shared by strategies 1 (```python) and 2 (generic).
# Kept private — they are internal contract for these two strategies only.
# ---------------------------------------------------------------------------


def _normalize_block_indent(block: str) -> str:
    """Strip the common leading whitespace from a code block.

    Empty or whitespace-only lines are preserved as empty strings (not
    dropped) so the resulting line count matches the input. Non-empty
    lines are dedented to the minimum indent across all non-empty lines.
    Tabs are expanded to 4 spaces before the calculation, matching the
    behavior of common code-block renderers.

    Returns an empty string when the block has no non-empty content.
    """
    lines = block.expandtabs(4).split("\n")
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return ""
    min_indent = min(len(line) - len(line.lstrip()) for line in non_empty)
    fixed_lines: list[str] = []
    for line in lines:
        if line.strip():
            fixed_lines.append(line[min_indent:])
        else:
            fixed_lines.append("")
    return "\n".join(fixed_lines).strip()


def _dedup_filename(fname: str, seen: dict[str, int]) -> str:
    """Return a unique filename, appending ``_N`` to the stem on collision.

    The first occurrence of ``fname`` is returned unchanged. Subsequent
    occurrences get ``_2``, ``_3``... inserted before the last extension
    (``foo.py`` → ``foo_2.py``). Filenames without an extension get the
    suffix appended to the end (``Makefile`` → ``Makefile_2``).

    The ``seen`` dict is mutated in place: the counter for ``fname`` is
    set to 1 on first use and incremented on each collision.
    """
    if fname in seen:
        seen[fname] += 1
        dot_idx = fname.rfind(".")
        if dot_idx != -1:
            return f"{fname[:dot_idx]}_{seen[fname]}{fname[dot_idx:]}"
        return f"{fname}_{seen[fname]}"
    seen[fname] = 1
    return fname


def _validate_python_block(name: str, content: str) -> str:
    """Validate a Python block; return the best salvage on failure.

    Delegates to ``ExtractedFile`` (which compiles the content, with
    internal dedent / fix_indent / fix_syntax fallback chain). On
    ``ValueError`` — i.e. when even the salvage chain inside
    ``ExtractedFile`` failed — falls back to ``textwrap.dedent`` so the
    caller still gets a non-empty string to work with. The result is
    never None; callers should check ``.strip()`` for emptiness.
    """
    try:
        return ExtractedFile(name=name, content=content).content
    except ValueError:
        return textwrap.dedent(content).strip()


def _validate_generic_block(name: str, content: str) -> str:
    """Validate a non-Python block; warn and return content on failure.

    Generic (non-Python, non-JSON) files don't get a compilation step,
    so a ``ValueError`` from ``ExtractedFile`` means the *filename* is
    invalid (unsupported extension or unsafe characters). The content
    itself is still potentially useful, so we log a warning and return
    it as-is rather than dropping the file.
    """
    try:
        return ExtractedFile(name=name, content=content).content
    except ValueError:
        logger.warning("Generic block '%s' failed validation: keeping raw", name)
        return content


def extract_code_dict(response: str) -> dict[str, Any]:
    """Multi-strategy extraction of {"files": {"name.py": "code"}} from raw LLM output.

    Strategies:
    1. Extract ```python code blocks
    2. Extract generic ```<language> blocks (powershell, bash, js, etc.)
    3. Extract ```json blocks (common LLM format)
    4. Direct JSON parse of cleaned response
    5. Find JSON object with "files" key (stack-based brace matching)
    6. Direct Python code detection
    7. Fallback: return raw response as main.py

    Returns:
        dict with "files" key mapping filenames to code strings
    """
    raw = response.strip()

    if not raw:
        logger.warning(
            "extract_code_dict received EMPTY response — coding_node LLM call "
            "likely timed out or the model returned no content. Returning empty files dict."
        )
        return {"steps": [], "files": {}}

    response_clean = _strip_llm_preamble(raw)
    if response_clean != raw:
        logger.info("LLM preamble stripped (%d chars removed)", len(raw) - len(response_clean))

    code_dict: dict[str, Any] | None = None

    # Strategy 1: Extract ```python blocks
    if code_dict is None:
        code_dict = _strategy_python_blocks(response_clean)

    # Strategy 2: Extract generic ```<language> blocks (powershell, bash, etc.)
    if code_dict is None:
        code_dict = _strategy_generic_blocks(response_clean)

    response_clean = re.sub(
        r"^```(?:json|python)?\s*", "", response_clean, flags=re.MULTILINE
    )
    response_clean = re.sub(r"\s*```$", "", response_clean)
    response_clean = response_clean.strip()

    # Strategy 3: Extract ```json blocks
    if code_dict is None:
        code_dict = _strategy_json_blocks(response_clean)

    # Strategy 4: Direct JSON parse
    if code_dict is None:
        code_dict = _strategy_direct_json(response_clean)

    # Strategy 5: Brace-matched JSON with "files" key
    if code_dict is None:
        code_dict = _strategy_brace_json(response_clean)

    # Strategy 6: Direct Python code detection
    if code_dict is None:
        code_dict = _strategy_pure_python(response_clean)

    # Fallback (Strategy 7)
    if code_dict is None:
        code_dict = {"steps": [], "files": {"main.py": response_clean}}
        logger.info("Fallback (strategy 7): raw response as main.py (%d chars)", len(response_clean))

    # Ensure 'steps' key exists for downstream code that expects it
    if "steps" not in code_dict:
        code_dict["steps"] = []

    # Final validation — salvage chain
    return _finalize(code_dict)


def _extract_filename_from_header(text: str, block_start: int) -> str | None:
    """Look for '## filename.ext' header on the line before a code block.

    Searches backward from block_start for a '## name.ext' pattern
    on the nearest non-empty line. Accepts any extension.
    """
    before = text[:block_start].rstrip()
    lines = before.split("\n")
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^##\s+([\w./-]+\.[\w]+)\s*$", line)
        if m:
            return m.group(1)
        # Also accept '# filename: file.ext'
        m = re.match(r"^#\s*filename:\s*([\w./-]+\.[\w]+)\s*$", line)
        if m:
            return m.group(1)
        # Also accept '// filename.ext' (JS/TS comment style)
        m = re.match(r"^//\s+([\w./-]+\.[\w]+)\s*$", line)
        if m:
            return m.group(1)
        break  # stop at first non-empty line before block
    return None


def _strategy_python_blocks(text: str) -> dict[str, Any] | None:
    """Strategy 1: Extract ```python code blocks with filenames."""
    # Find all ```python blocks with their positions
    blocks: list[tuple[int, str]] = []
    for m in re.finditer(r"```python\s*([\s\S]*?)```", text):
        blocks.append((m.start(), m.group(1)))

    if not blocks:
        return None

    files: dict[str, str] = {}
    seen_names: dict[str, int] = {}

    for block_start, block_content in blocks:
        if not block_content.strip():
            continue

        # Filename: prefer `## name.ext` header before the block, else
        # auto-generate `file_N.py` (deduped on collision).
        fname = _extract_filename_from_header(text, block_start)
        if not fname:
            fname = f"file_{len(files) + 1}.py"
        fname = _dedup_filename(fname, seen_names)

        normalized = _normalize_block_indent(block_content)
        if not normalized:
            continue
        normalized = _validate_python_block(fname, normalized)

        if normalized.strip():
            files[fname] = normalized + "\n"

    if not files:
        return None
    logger.info("Strategy 1 (```python blocks): %d files extracted", len(files))
    return {"files": files}


def _strategy_generic_blocks(text: str) -> dict[str, Any] | None:
    """Strategy 2: Extract generic ```<language> code blocks (non-Python, non-JSON).

    Maps language identifiers (powershell, bash, js, etc.) to file extensions.
    Looks for ## filename.ext headers before the block.
    """
    blocks: list[tuple[int, str, str]] = []
    for m in re.finditer(r"```(\w+)\s*\n([\s\S]*?)```", text):
        lang = m.group(1).lower()
        # Skip python and json — handled by strategies 1 & 3
        if lang in ("python", "py", "json"):
            continue
        blocks.append((m.start(), lang, m.group(2)))

    if not blocks:
        return None

    files: dict[str, str] = {}
    seen_names: dict[str, int] = {}

    for block_start, lang, block_content in blocks:
        if not block_content.strip():
            continue

        # Filename: prefer `## name.ext` header, else `script.<ext>` where
        # <ext> is mapped from the language id (powershell -> .ps1, etc.).
        fname = _extract_filename_from_header(text, block_start)
        if not fname:
            ext = LANG_EXTENSIONS.get(lang, f".{lang}")
            fname = f"script{ext}"
        fname = _dedup_filename(fname, seen_names)

        normalized = _normalize_block_indent(block_content)
        if not normalized:
            continue
        normalized = _validate_generic_block(fname, normalized)

        if normalized.strip():
            files[fname] = normalized + "\n"

    if not files:
        return None
    logger.info("Strategy 2 (generic code blocks): %d file(s) extracted", len(files))
    return {"files": files}


def _strategy_json_blocks(text: str) -> dict[str, Any] | None:
    """Strategy 3: Extract ```json blocks."""
    json_blocks = re.findall(r"```json\s*([\s\S]*?)```", text)
    for block in json_blocks:
        try:
            candidate = json.loads(block.strip())
            if isinstance(candidate, dict) and "files" in candidate:
                extracted = ExtractedCode.model_validate(candidate)
                logger.info("Strategy 3 (```json blocks): %d files extracted", len(candidate["files"]))
                return extracted.to_dict()
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            continue
    return None


def _strategy_direct_json(text: str) -> dict[str, Any] | None:
    """Strategy 4: Direct JSON parse of the whole response."""
    try:
        candidate = json.loads(text)
        if isinstance(candidate, dict) and "files" in candidate:
            extracted = ExtractedCode.model_validate(candidate)
            logger.info("Strategy 4 (direct JSON): %d files extracted", len(candidate["files"]))
            return extracted.to_dict()
    except (json.JSONDecodeError, ValueError, TypeError, KeyError):
        pass
    return None


def _strategy_brace_json(text: str) -> dict[str, Any] | None:
    """Strategy 5: Find JSON object with 'files' key via brace counter."""
    json_objects = _find_json_objects(text)
    for obj_str in json_objects:
        try:
            candidate = json.loads(obj_str)
            if not (isinstance(candidate, dict) and "files" in candidate):
                continue
            files = candidate["files"]
            if not (isinstance(files, dict) and all(isinstance(v, str) for v in files.values())):
                continue
            valid_files: dict[str, str] = {}
            for fname, fcontent in files.items():
                try:
                    ExtractedFile(name=fname, content=fcontent)
                    valid_files[fname] = fcontent
                except ValueError:
                    dedented = textwrap.dedent(fcontent).strip()
                    try:
                        ExtractedFile(name=fname, content=dedented)
                        valid_files[fname] = dedented + "\n"
                    except ValueError:
                        pass
            if valid_files:
                logger.info("Strategy 5 (brace-matched JSON): %d files extracted", len(valid_files))
                return {"files": valid_files}
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
    return None


def _strategy_pure_python(text: str) -> dict[str, Any] | None:
    """Strategy 6: Detect and return pure Python code."""
    py_start = re.match(r"^\s*(?:def\s+\w+|class\s+\w+|import\s+|from\s+)", text)
    if py_start:
        logger.info("Strategy 6 (pure Python detected): main.py")
        return {"files": {"main.py": text}}
    return None


def _finalize(code_dict: dict[str, Any]) -> dict[str, Any]:
    """Final validation with salvage chain.

    When a file has an unsupported extension (e.g. `py.typed` not in
    the whitelist) the content fixes below won't help — the filename
    itself is invalid.  In that case we **drop** the offending files
    so the rest of the extraction survives instead of returning raw
    content with invalid entries.
    """
    try:
        extracted = ExtractedCode.model_validate(code_dict)
        return extracted.to_dict()
    except ValueError as e:
        logger.warning("Final validation failed: %s — attempting salvage...", e)

        if "files" in code_dict:
            # Rebuild with only validly-named files first (content may still
            # fail, but at least the filename check passes). This handles
            # unsupported extensions like `.typed` without dropping
            # everything downstream.
            valid_names: dict[str, str] = {}
            invalid_names: list[str] = []
            for fname, fcontent in code_dict["files"].items():
                try:
                    ExtractedFile(name=fname, content=fcontent or "")
                    valid_names[fname] = str(fcontent)
                except ValueError:
                    invalid_names.append(fname)

            if invalid_names:
                logger.warning(
                    "Dropping %d invalid file(s) during salvage: %s",
                    len(invalid_names),
                    ", ".join(invalid_names),
                )
                if valid_names:
                    try:
                        extracted = ExtractedCode.model_validate({"files": valid_names})
                        logger.info(
                            "Salvaged by dropping %d invalid file(s): %d file(s) remaining",
                            len(invalid_names),
                            len(valid_names),
                        )
                        return extracted.to_dict()
                    except ValueError:
                        pass

            # Salvage 1: fix indentation on Python files only
            # (fix_indentation uses compile() internally — not safe for .ps1, .sh, etc.)
            salvaged: dict[str, str] = {}
            for fname, fcontent in code_dict["files"].items():
                if isinstance(fcontent, str) and fname.endswith(tuple(_PYTHON_EXTENSIONS)):
                    salvaged[fname] = fix_indentation(fcontent)
            if salvaged:
                try:
                    extracted = ExtractedCode.model_validate({"files": salvaged})
                    logger.info("Salvaged via indentation fix: %d files", len(salvaged))
                    return extracted.to_dict()
                except ValueError:
                    pass

            # Salvage 2: syntax repair — Python files only (uses compile() internally)
            repaired_salvage: dict[str, str] = {}
            for fname, fcontent in code_dict["files"].items():
                if isinstance(fcontent, str) and fname.endswith(tuple(_PYTHON_EXTENSIONS)):
                    repaired_salvage[fname] = fix_syntax_errors(fcontent)
            if repaired_salvage:
                try:
                    extracted = ExtractedCode.model_validate({"files": repaired_salvage})
                    logger.info("Salvaged via syntax repair: %d files", len(repaired_salvage))
                    return extracted.to_dict()
                except ValueError:
                    pass

        logger.warning("All salvage attempts failed — returning raw content")
        return code_dict
