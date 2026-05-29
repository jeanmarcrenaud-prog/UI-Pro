"""Extract valid Python code dict from LLM response with Pydantic validation."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field, field_validator, model_validator

# Taille maximale d'un fichier extrait (500KB)
MAX_FILE_SIZE = 500_000

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
        # Ignorer les lignes vides et les préambules
        if not stripped:
            continue
        if _LLM_PREAMBLE_PATTERNS.match(stripped):
            code_start = i + 1
        elif stripped.startswith(("```", "{", "import ", "from ", "def ", "class ", "print")):
            # Premier signe de code valide → fin du préambule
            break
        else:
            # Ligne non reconnue comme préambule → on garde
            code_start = i
            break
    trimmed = "\n".join(lines[code_start:]).strip()
    return trimmed if trimmed else text


def _find_json_objects(text: str) -> list[str]:
    """Trouve les objets JSON de premier niveau par compteur d'accolades.

    Plus performant et fiable que re.findall(r'\{[\s\S]*?\}', ...)
    qui est lent sur les grosses réponses et ne gère pas bien l'imbrication.
    """
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
                # Évite de compter les accolades dans les strings
                if text[i] in ("'", '"'):
                    quote = text[i]
                    i += 1
                    while i < len(text) and text[i] != quote:
                        if text[i] == "\\":
                            i += 1  # skip escaped char
                        i += 1
                i += 1
            if depth == 0:
                objects.append(text[start:i])
        else:
            i += 1
    return objects


def _fix_syntax_errors(code: str) -> str:
    """Attempt basic syntax repair for common LLM mistakes.

    Tries to:
    1. Remove extra closing brackets (parens, brackets, braces)
    2. Append missing closing brackets at the end

    Returns the best-effort fixed code, or the original if no fix is needed.
    """
    stripped = code.strip()
    if not stripped:
        return code

    # Try compiling as-is first
    try:
        compile(stripped, "<string>", "exec")
        return code
    except SyntaxError:
        pass

    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = set(pairs.values())

    # Strategy 1: Scan and remove extra closing brackets
    for _ in range(3):  # Try up to 3 iterations
        stack = []
        cleaned: list[str] = []
        for ch in stripped:
            if ch in pairs:
                stack.append(ch)
                cleaned.append(ch)
            elif ch in closing:
                if stack and pairs.get(stack[-1]) == ch:
                    stack.pop()
                    cleaned.append(ch)
                # else: extra closing bracket - remove it (don't append)
            else:
                cleaned.append(ch)
        candidate = "".join(cleaned)
        if candidate == stripped and stack:
            # No brackets were removed but there are unmatched opening brackets
            # Append missing closing brackets
            extra_closers = "".join(pairs[opener] for opener in reversed(stack))
            candidate = stripped + extra_closers

        try:
            compile(candidate, "<string>", "exec")
            return candidate
        except SyntaxError:
            stripped = candidate
            continue

    return code  # All repair attempts failed


def _fix_indentation(code: str) -> str:
    """Normalize inconsistent indentation.

    Strategy: bump outlier lines to the minimum non-zero indent,
    then dedent everything to column 0.

    Example:
        import requests       <- outlier (indent 0, should be 4)
        import json           <- ok (indent 4)
        from datetime import... <- ok (indent 4)
        url = "..."           <- ok (indent 4)
        params = {            <- ok (indent 4)
            "key": "val"      <- deeper indent (8) - preserved after dedent
    """
    lines = code.split("\n")
    non_empty = [l for l in lines if l.strip()]
    if len(non_empty) < 2:
        return code

    indents = [len(l) - len(l.lstrip()) for l in non_empty]
    nonzero = [i for i in indents if i > 0]
    if not nonzero:
        return code

    # Use the MINIMUM non-zero indent as the base level
    # (not the most common - nested blocks often have more lines)
    base_indent = min(nonzero)
    min_indent = min(indents)

    candidates: list[str] = []

    # Strategy 1: bump lines below base_indent up, dedent all to 0
    if min_indent < base_indent:
        fixed: list[str] = []
        for line in lines:
            if line.strip():
                diff = len(line) - len(line.lstrip())
                if diff < base_indent:
                    fixed.append(" " * base_indent + line.lstrip())
                else:
                    fixed.append(line)
            else:
                fixed.append(line)
        uniform = "\n".join(fixed)
        # Dedent to remove common base_indent whitespace
        dedented = textwrap.dedent(uniform)
        if dedented != uniform:
            candidates.append(dedented)
        candidates.append(uniform)

    # Strategy 2: simple textwrap.dedent
    dedented_full = textwrap.dedent(code)
    if dedented_full != code:
        candidates.append(dedented_full)

    # Try each candidate, return first that compiles
    for candidate in candidates:
        try:
            compile(candidate, "<string>", "exec")
            return candidate
        except SyntaxError:
            continue

    return code


class ExtractedFile(BaseModel):
    """Validated file content with name and syntax check."""

    name: str = Field(..., description="File name with .py extension")
    content: str = Field(..., description="Python file content")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure filename ends with .py and is safe."""
        if not v.endswith(".py"):
            raise ValueError(f"Filename must end with .py, got: {v}")
        # Allow path separators for nested directories
        safe_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/_-."
        )
        if not all(c in safe_chars for c in v):
            raise ValueError(f"Filename contains invalid characters: {v}")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content is valid Python or empty."""
        if len(v) > MAX_FILE_SIZE:
            raise ValueError(f"Code too large ({len(v)} bytes > {MAX_FILE_SIZE} limit)")
        stripped = v.strip()
        if not stripped:
            return v
        # Try to compile the content
        try:
            compile(stripped, v, "exec")
        except SyntaxError as e:
            # Try with dedented content
            dedented = textwrap.dedent(stripped)
            try:
                compile(dedented, v, "exec")
                return dedented
            except SyntaxError:
                # Aggressive fix: re-indent all lines based on the majority indent
                fixed = _fix_indentation(stripped)
                try:
                    compile(fixed, v, "exec")
                    return fixed
                except SyntaxError:
                    # Try basic syntax repair (balance parens/brackets)
                    repaired = _fix_syntax_errors(fixed)
                    try:
                        compile(repaired, v, "exec")
                        return repaired
                    except SyntaxError:
                        logger.warning(
                            "Syntax error in generated code: %s at line %s",
                            e.msg,
                            e.lineno,
                        )
                        raise ValueError(f"Invalid Python syntax: {e}")
        return v


class ExtractedCode(BaseModel):
    """Validated extraction result with files dictionary."""

    files: dict[str, str] = Field(..., description="Mapping of filename to content")

    @model_validator(mode="after")
    def validate_files(self) -> ExtractedCode:
        """Validate all files have proper names and content."""
        if not self.files:
            raise ValueError("At least one file is required")
        validated: dict[str, str] = {}
        for fname, fcontent in self.files.items():
            try:
                file_model = ExtractedFile(name=fname, content=fcontent)
                validated[file_model.name] = file_model.content
            except Exception as e:
                raise ValueError(f"Invalid file '{fname}': {e}")
        # Replace with validated entries (normalized names)
        object.__setattr__(self, "files", validated)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dict for backward compatibility."""
        return {"files": self.files}


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
    # 1) Pré-nettoyage : supprimer le préambule "Thinking Process"
    response_clean = _strip_llm_preamble(raw)
    if response_clean != raw:
        logger.info("LLM preamble stripped (%d chars removed)", len(raw) - len(response_clean))

    code_dict: dict[str, Any] | None = None

    # Strategy 1: Extract ```python blocks
    if code_dict is None:
        py_blocks = re.findall(r"```python\s*([\s\S]*?)```", response_clean)
        if py_blocks:
            files: dict[str, str] = {}
            for i, block in enumerate(py_blocks):
                block = block.strip()
                if not block:
                    continue
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
                    validated = ExtractedFile(
                        name=f"file_{i + 1}.py", content=normalized
                    )
                    normalized = validated.content
                except ValueError:
                    fixed = _fix_indentation(normalized)
                    try:
                        validated = ExtractedFile(
                            name=f"file_{i + 1}.py", content=fixed
                        )
                        normalized = validated.content
                    except ValueError:
                        normalized = textwrap.dedent(normalized).strip()
                if normalized.strip():
                    files[f"file_{i + 1}.py"] = normalized + "\n"
            if files:
                code_dict = {"files": files}
                logger.info("Strategy 1 (```python blocks): %d files extracted", len(files))

    # Strip ``` markers for remaining strategies
    response_clean = re.sub(
        r"^```(?:json|python)?\s*", "", response_clean, flags=re.MULTILINE
    )
    response_clean = re.sub(r"\s*```$", "", response_clean)
    response_clean = response_clean.strip()

    # Strategy 2: Extract ```json blocks
    if code_dict is None:
        json_blocks = re.findall(r"```json\s*([\s\S]*?)```", response_clean)
        for block in json_blocks:
            try:
                candidate = json.loads(block.strip())
                if isinstance(candidate, dict) and "files" in candidate:
                    extracted = ExtractedCode.model_validate(candidate)
                    code_dict = extracted.to_dict()
                    logger.info("Strategy 2 (```json blocks): %d files extracted", len(candidate["files"]))
                    break
            except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                continue

    # Strategy 3: Direct JSON parse of the whole response
    if code_dict is None:
        try:
            candidate = json.loads(response_clean)
            if isinstance(candidate, dict) and "files" in candidate:
                extracted = ExtractedCode.model_validate(candidate)
                code_dict = extracted.to_dict()
                logger.info("Strategy 3 (direct JSON): %d files extracted", len(candidate["files"]))
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            pass

    # Strategy 4: Find JSON object with "files" key (brace counter)
    if code_dict is None:
        json_objects = _find_json_objects(response_clean)
        for obj_str in json_objects:
            try:
                candidate = json.loads(obj_str)
                if isinstance(candidate, dict) and "files" in candidate:
                    files = candidate["files"]
                    if isinstance(files, dict) and all(
                        isinstance(v, str) for v in files.values()
                    ):
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
                            code_dict = {"files": valid_files}
                            logger.info("Strategy 4 (brace-matched JSON): %d files extracted", len(valid_files))
                            break
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

    # Strategy 5: Direct Python code detection
    if code_dict is None:
        py_start = re.match(
            r"^\s*(?:def\s+\w+|class\s+\w+|import\s+|from\s+)",
            response_clean,
        )
        if py_start:
            code_dict = {"files": {"main.py": response_clean}}
            logger.info("Strategy 5 (pure Python detected): main.py")

    # Fallback
    if code_dict is None:
        code_dict = {"files": {"main.py": response_clean}}
        logger.info("Fallback: raw response as main.py (%d chars)", len(response_clean))

    # Final validation — salvage chain
    try:
        extracted = ExtractedCode.model_validate(code_dict)
        return extracted.to_dict()
    except ValueError as e:
        logger.warning("Final validation failed: %s — attempting salvage...", e)

        # Salvage 1: fix indentation
        if "files" in code_dict:
            salvaged: dict[str, str] = {}
            for fname, fcontent in code_dict["files"].items():
                if isinstance(fcontent, str):
                    fixed = _fix_indentation(fcontent)
                    salvaged[fname] = fixed
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
                    repaired = _fix_syntax_errors(fcontent)
                    repaired_salvage[fname] = repaired
            if repaired_salvage:
                try:
                    extracted = ExtractedCode.model_validate({"files": repaired_salvage})
                    logger.info("Salvaged via syntax repair: %d files", len(repaired_salvage))
                    return extracted.to_dict()
                except ValueError:
                    pass

        logger.warning("All salvage attempts failed — returning raw content")
        return code_dict
