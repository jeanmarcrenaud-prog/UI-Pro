"""Multi-strategy extraction of code dicts from raw LLM output."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from typing import Any

from .models import ExtractedCode, ExtractedFile
from .repair import fix_indentation, fix_syntax_errors

logger = logging.getLogger(__name__)

# Préambules LLM fréquents à ignorer
_LLM_PREAMBLE_PATTERNS = re.compile(
    r"^(#|//|-\s*)?(Thinking|Analyzing|Reasoning|Here'?s|Here is|Let me|I'?ll|The (solution|code|approach|best)|Code[:\s]|Voici|Je vais|Analyse)",
    re.IGNORECASE,
)


def _strip_llm_preamble(text: str) -> str:
    """Supprime le préambule 'Thinking Process' ou 'Here's the code' des réponses LLM."""
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
    """Trouve les objets JSON de premier niveau par compteur d'accolades."""
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


def extract_code_dict(response: str) -> dict[str, Any]:
    """Multi-strategy extraction of {"files": {"name.py": "code"}} from raw LLM output.

    Strategies:
    1. Extract ```python code blocks
    2. Extract ```json blocks (common LLM format)
    3. Direct JSON parse of cleaned response
    4. Find JSON object with "files" key (stack-based brace matching)
    5. Direct Python code detection
    6. Fallback: return raw response as main.py

    Returns:
        dict with "files" key mapping filenames to Python code strings
    """
    raw = response.strip()
    response_clean = _strip_llm_preamble(raw)
    if response_clean != raw:
        logger.info("LLM preamble stripped (%d chars removed)", len(raw) - len(response_clean))

    code_dict: dict[str, Any] | None = None

    # Strategy 1: Extract ```python blocks
    if code_dict is None:
        code_dict = _strategy_python_blocks(response_clean)

    response_clean = re.sub(
        r"^```(?:json|python)?\s*", "", response_clean, flags=re.MULTILINE
    )
    response_clean = re.sub(r"\s*```$", "", response_clean)
    response_clean = response_clean.strip()

    # Strategy 2: Extract ```json blocks
    if code_dict is None:
        code_dict = _strategy_json_blocks(response_clean)

    # Strategy 3: Direct JSON parse
    if code_dict is None:
        code_dict = _strategy_direct_json(response_clean)

    # Strategy 4: Brace-matched JSON with "files" key
    if code_dict is None:
        code_dict = _strategy_brace_json(response_clean)

    # Strategy 5: Direct Python code detection
    if code_dict is None:
        code_dict = _strategy_pure_python(response_clean)

    # Fallback
    if code_dict is None:
        code_dict = {"files": {"main.py": response_clean}}
        logger.info("Fallback: raw response as main.py (%d chars)", len(response_clean))

    # Final validation — salvage chain
    return _finalize(code_dict)


def _extract_filename_from_header(text: str, block_start: int) -> str | None:
    """Look for '## filename.py' header on the line before a ```python block.

    Searches backward from block_start for a '## name.py' pattern
    on the nearest non-empty line.
    """
    before = text[:block_start].rstrip()
    lines = before.split("\n")
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^##\s+([\w./-]+\.py)\s*$", line)
        if m:
            return m.group(1)
        # Also accept '# filename: file.py'
        m = re.match(r"^#\s*filename:\s*([\w./-]+\.py)\s*$", line)
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
        block = block_content.strip()
        if not block:
            continue

        # Try to extract filename from header before the block
        fname = _extract_filename_from_header(text, block_start)
        if not fname:
            fname = f"file_{len(files) + 1}.py"

        # Deduplicate filenames
        if fname in seen_names:
            seen_names[fname] += 1
            base, ext = fname.rsplit(".", 1)
            fname = f"{base}_{seen_names[fname]}.{ext}"
        else:
            seen_names[fname] = 1

        # Normalize indentation
        lines = block.expandtabs(4).split("\n")
        non_empty = [l for l in lines if l.strip()]
        if not non_empty:
            continue
        min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
        fixed_lines: list[str] = []
        for line in lines:
            if line.strip():
                fixed_lines.append(line[min_indent:])
            else:
                fixed_lines.append("")
        normalized = "\n".join(fixed_lines).strip()

        try:
            validated = ExtractedFile(name=fname, content=normalized)
            normalized = validated.content
        except ValueError:
            fixed = fix_indentation(normalized)
            try:
                validated = ExtractedFile(name=fname, content=fixed)
                normalized = validated.content
            except ValueError:
                normalized = textwrap.dedent(normalized).strip()

        if normalized.strip():
            files[fname] = normalized + "\n"

    if not files:
        return None
    logger.info("Strategy 1 (```python blocks): %d files extracted", len(files))
    return {"files": files}


def _strategy_json_blocks(text: str) -> dict[str, Any] | None:
    """Strategy 2: Extract ```json blocks."""
    json_blocks = re.findall(r"```json\s*([\s\S]*?)```", text)
    for block in json_blocks:
        try:
            candidate = json.loads(block.strip())
            if isinstance(candidate, dict) and "files" in candidate:
                extracted = ExtractedCode.model_validate(candidate)
                logger.info("Strategy 2 (```json blocks): %d files extracted", len(candidate["files"]))
                return extracted.to_dict()
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            continue
    return None


def _strategy_direct_json(text: str) -> dict[str, Any] | None:
    """Strategy 3: Direct JSON parse of the whole response."""
    try:
        candidate = json.loads(text)
        if isinstance(candidate, dict) and "files" in candidate:
            extracted = ExtractedCode.model_validate(candidate)
            logger.info("Strategy 3 (direct JSON): %d files extracted", len(candidate["files"]))
            return extracted.to_dict()
    except (json.JSONDecodeError, ValueError, TypeError, KeyError):
        pass
    return None


def _strategy_brace_json(text: str) -> dict[str, Any] | None:
    """Strategy 4: Find JSON object with 'files' key via brace counter."""
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
                logger.info("Strategy 4 (brace-matched JSON): %d files extracted", len(valid_files))
                return {"files": valid_files}
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
    return None


def _strategy_pure_python(text: str) -> dict[str, Any] | None:
    """Strategy 5: Detect and return pure Python code."""
    py_start = re.match(r"^\s*(?:def\s+\w+|class\s+\w+|import\s+|from\s+)", text)
    if py_start:
        logger.info("Strategy 5 (pure Python detected): main.py")
        return {"files": {"main.py": text}}
    return None


def _finalize(code_dict: dict[str, Any]) -> dict[str, Any]:
    """Final validation with salvage chain."""
    try:
        extracted = ExtractedCode.model_validate(code_dict)
        return extracted.to_dict()
    except ValueError as e:
        logger.warning("Final validation failed: %s — attempting salvage...", e)

        if "files" in code_dict:
            # Salvage 1: fix indentation
            salvaged: dict[str, str] = {}
            for fname, fcontent in code_dict["files"].items():
                if isinstance(fcontent, str):
                    salvaged[fname] = fix_indentation(fcontent)
            if salvaged:
                try:
                    extracted = ExtractedCode.model_validate({"files": salvaged})
                    logger.info("Salvaged via indentation fix: %d files", len(salvaged))
                    return extracted.to_dict()
                except ValueError:
                    pass

            # Salvage 2: syntax repair
            repaired_salvage: dict[str, str] = {}
            for fname, fcontent in code_dict["files"].items():
                if isinstance(fcontent, str):
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
