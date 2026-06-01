"""Pydantic models for extracted code with validation and security checks."""

from __future__ import annotations

import logging
import textwrap
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Taille maximale d'un fichier extrait (500KB)
MAX_FILE_SIZE = 500_000

# Extensions for which we attempt Python compile() validation
_PYTHON_EXTENSIONS = {".py", ".pyw"}

# Allowed file extensions for extracted code blocks
_VALID_EXTENSIONS = _PYTHON_EXTENSIONS | {
    ".ps1", ".psm1", ".psd1",        # PowerShell
    ".sh", ".bash", ".zsh",          # Shell
    ".bat", ".cmd",                  # Batch
    ".js", ".mjs", ".cjs",           # JavaScript
    ".ts", ".mts", ".cts",           # TypeScript
    ".jsx", ".tsx",                  # JSX/TSX
    ".html", ".htm",                 # HTML
    ".css", ".scss", ".less",        # Styles
    ".json", ".jsonc",               # JSON
    ".yaml", ".yml",                 # YAML
    ".toml",                         # TOML
    ".ini", ".cfg", ".conf",         # Config
    ".xml", ".svg",                  # XML
    ".sql",                          # SQL
    ".md", ".mdx",                   # Markdown
    ".env",                          # Env
    ".dockerfile", "Dockerfile",     # Docker
    ".rs",                           # Rust
    ".go",                           # Go
    ".java",                         # Java
    ".c", ".cpp", ".cxx", ".h", ".hpp",  # C/C++
    ".rb",                           # Ruby
    ".php",                          # PHP
    ".swift",                        # Swift
    ".kt", ".kts",                   # Kotlin
    ".scala",                        # Scala
    ".r", ".R",                      # R
    ".lua",                          # Lua
    ".pl", ".pm",                    # Perl
    ".cs",                           # C#
    ".fs",                           # F#
    ".zig",                          # Zig
    ".nim",                          # Nim
    ".ex", ".exs",                   # Elixir
    ".erl", ".hrl",                  # Erlang
    ".hs", ".lhs",                   # Haskell
    ".clj", ".cljs", ".edn",        # Clojure
    ".txt",                          # Plain text
    "Makefile", "makefile",          # Make
}

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

    name: str = Field(..., description="File name with extension")
    content: str = Field(..., description="File content")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure filename has a supported extension and safe characters."""
        safe_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/_-."
        )
        if not all(c in safe_chars for c in v):
            raise ValueError(f"Filename contains invalid characters: {v}")

        has_valid_ext = any(v.endswith(ext) for ext in _VALID_EXTENSIONS)
        if not has_valid_ext:
            raise ValueError(
                f"Unsupported file extension in '{v}'. "
                f"Allowed: {', '.join(sorted(_VALID_EXTENSIONS))}"
            )
        return v

    @model_validator(mode="after")
    def validate_content(self) -> ExtractedFile:
        """Validate content — Python files get compiled, others pass through."""
        v = self.content
        if len(v) > MAX_FILE_SIZE:
            raise ValueError(
                f"Content too large ({len(v)} bytes > {MAX_FILE_SIZE} limit)"
            )
        stripped = v.strip()
        if not stripped:
            return self

        # Soft security check (warning only)
        log_dangerous_patterns(stripped, context=self.name)

        # Skip Python compilation for non-Python files
        if not any(self.name.endswith(ext) for ext in _PYTHON_EXTENSIONS):
            return self

        # Try to compile as Python
        try:
            compile(stripped, self.name, "exec")
        except SyntaxError as e:
            # Try with dedented content
            dedented = textwrap.dedent(stripped)
            try:
                compile(dedented, self.name, "exec")
                self.content = dedented
                return self
            except SyntaxError:
                from .repair import fix_indentation as _fix_indent
                from .repair import fix_syntax_errors as _fix_syntax

                # Aggressive fix: re-indent all lines based on the majority indent
                fixed = _fix_indent(stripped)
                try:
                    compile(fixed, self.name, "exec")
                    self.content = fixed
                    return self
                except SyntaxError:
                    # Try basic syntax repair (balance parens/brackets)
                    repaired = _fix_syntax(fixed)
                    try:
                        compile(repaired, self.name, "exec")
                        self.content = repaired
                        return self
                    except SyntaxError:
                        logger.warning(
                            "Syntax error in generated code: %s at line %s",
                            e.msg,
                            e.lineno,
                        )
                        raise ValueError(f"Invalid Python syntax in '{self.name}': {e}")
        return self


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
