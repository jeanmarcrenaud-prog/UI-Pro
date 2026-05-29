"""Pydantic models for extracted code with validation and security checks."""

from __future__ import annotations

import logging
import textwrap
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Taille maximale d'un fichier extrait (500KB)
MAX_FILE_SIZE = 500_000

# Patterns dangereux à logger (sécurité au niveau extraction)
DANGEROUS_PATTERNS: list[str] = [
    "os.system",
    "subprocess.",
    "eval(",
    "exec(",
    "__import__",
]


def log_dangerous_patterns(code: str, context: str = "") -> list[str]:
    """Log warning if dangerous patterns detected in extracted code.

    This is a soft check — it does NOT block execution (runtime isolation
    in DockerSandbox/SubprocessExecutor handles that). It just alerts
    developers during debugging.
    """
    found = [kw for kw in DANGEROUS_PATTERNS if kw.lower() in code.lower()]
    if found:
        tag = f" [{context}]" if context else ""
        logger.warning("Code contains dangerous patterns%s: %s", tag, found)
    return found


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
        # Soft security check (warning only — runtime isolation handles blocking)
        log_dangerous_patterns(stripped, context="validate_content")
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
                from .repair import fix_indentation as _fix_indent
                from .repair import fix_syntax_errors as _fix_syntax

                # Aggressive fix: re-indent all lines based on the majority indent
                fixed = _fix_indent(stripped)
                try:
                    compile(fixed, v, "exec")
                    return fixed
                except SyntaxError:
                    # Try basic syntax repair (balance parens/brackets)
                    repaired = _fix_syntax(fixed)
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
        object.__setattr__(self, "files", validated)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dict for backward compatibility."""
        return {"files": self.files}
