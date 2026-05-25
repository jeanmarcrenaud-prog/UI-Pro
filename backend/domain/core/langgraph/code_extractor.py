"""Extract valid Python code dict from LLM response with Pydantic validation."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field, field_validator, model_validator


def _fix_indentation(code: str) -> str:
    """Normalize inconsistent indentation (e.g. first line at col 0, rest at col 4+)."""
    lines = code.split("\n")
    non_empty = [l for l in lines if l.strip()]
    if len(non_empty) < 2:
        return code

    # Calculate indent per line (leading spaces)
    indents = [len(l) - len(l.lstrip()) for l in non_empty]
    # Find the most common non-zero indent as the baseline
    nonzero = [i for i in indents if i > 0]
    if not nonzero:
        return code

    baseline = max(set(nonzero), key=nonzero.count)
    # If any line has 0 indent while most have `baseline`, re-indent everything
    if min(indents) == 0 and baseline > 0:
        fixed: list[str] = []
        for line in lines:
            if line.strip():
                diff = len(line) - len(line.lstrip())
                if diff < baseline:
                    fixed.append(" " * baseline + line.lstrip())
                else:
                    fixed.append(line)
            else:
                fixed.append(line)
        return "\n".join(fixed)

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
    1. Direct JSON parse
    2. Find JSON object with "files" key (regex + validate syntax)
    3. Extract python code blocks
    4. Direct Python detection
    5. Fallback: return raw response as main.py

    Returns:
        dict with "files" key mapping filenames to Python code strings

    Raises:
        ValueError: If extraction fails all strategies
    """
    response_clean = response.strip()
    response_clean = re.sub(
        r"^```(?:json|python)?\s*", "", response_clean, flags=re.MULTILINE
    )
    response_clean = re.sub(r"\s*```$", "", response_clean)
    response_clean = response_clean.strip()

    code_dict: dict[str, Any] | None = None
    last_error: str | None = None

    # Strategy 1: Direct JSON parse
    if code_dict is None:
        try:
            candidate = json.loads(response_clean)
            if isinstance(candidate, dict) and "files" in candidate:
                extracted = ExtractedCode.model_validate(candidate)
                code_dict = extracted.to_dict()
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            last_error = str(e)

    # Strategy 2: Find JSON object with "files" key
    if code_dict is None:
        json_matches = re.findall(r"\{[\s\S]*?\}", response_clean)
        for match in json_matches:
            try:
                candidate = json.loads(match)
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
                                # Try dedenting
                                dedented = textwrap.dedent(fcontent).strip()
                                try:
                                    ExtractedFile(name=fname, content=dedented)
                                    valid_files[fname] = dedented + "\n"
                                except ValueError:
                                    pass
                        if valid_files:
                            code_dict = {"files": valid_files}
                            break
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

    # Strategy 3: Extract python code blocks
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
                    ExtractedFile(name=f"file_{i + 1}.py", content=normalized)
                except ValueError:
                    normalized = textwrap.dedent(normalized).strip()
                if normalized.strip():
                    files[f"file_{i + 1}.py"] = normalized + "\n"
            if files:
                code_dict = {"files": files}

    # Strategy 4: Direct Python code detection
    if code_dict is None:
        py_start = re.search(
            r"^def\s+\w+|^\s*def\s+\w+|^class\s+\w+|^import\s+|^from\s+",
            response_clean,
            re.MULTILINE,
        )
        if py_start:
            code_dict = {"files": {"main.py": response_clean.strip()}}

    # Fallback
    if code_dict is None:
        code_dict = {"files": {"main.py": response_clean}}

    # Final validation — don't crash, salvage what we can
    try:
        extracted = ExtractedCode.model_validate(code_dict)
        return extracted.to_dict()
    except ValueError as e:
        logger.warning("Code validation failed, returning fallback: %s", e)
        # Try to salvage by fixing indentation on all files
        if "files" in code_dict:
            salvaged: dict[str, str] = {}
            for fname, fcontent in code_dict["files"].items():
                if isinstance(fcontent, str):
                    fixed = _fix_indentation(fcontent)
                    salvaged[fname] = fixed
            if salvaged:
                try:
                    extracted = ExtractedCode.model_validate({"files": salvaged})
                    return extracted.to_dict()
                except ValueError:
                    pass
        # Last resort: return raw content as-is
        return code_dict
