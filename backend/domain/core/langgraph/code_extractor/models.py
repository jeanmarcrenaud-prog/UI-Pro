"""
code_extractor/models.py — Modèles Pydantic pour le code extrait avec validation.

Fonctionnement
--------------
1. ``ExtractedFile``  — Valide un fichier individuel (nom, contenu, compilation Python)
2. ``ExtractedCode``  — Valide un dictionnaire complet ``{files: {nom: contenu}}``
3. ``log_dangerous_patterns`` — Détecte les patterns à risque (os.system, eval, etc.)

La validation compile chaque fichier Python avec ``compile()`` pour détecter les erreurs
de syntaxe dès l'extraction, avant toute exécution. Une chaîne de réparation (dedent → 
``fix_indentation`` → ``fix_syntax_errors``) tente de corriger les erreurs LLM courantes.
"""

from __future__ import annotations

import logging
import textwrap
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Taille maximale d'un fichier extrait (500 Ko)
MAX_FILE_SIZE = 500_000

# Extensions pour lesquelles on tente une validation compile()
_PYTHON_EXTENSIONS = {".py", ".pyw"}

# Extensions pour lesquelles on tente une validation syntaxique de base
_VALIDATABLE_EXTENSIONS = _PYTHON_EXTENSIONS | {
    ".js", ".mjs", ".cjs",
    ".ts", ".mts", ".cts",
    ".jsx", ".tsx",
}

# Extensions autorisées — tout fichier en dehors de cette liste est rejeté
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
    ".typed",                        # PEP 561 marker (py.typed for typed packages)
    "Makefile", "makefile",          # Make
}

# Patterns à risque détectés à l'extraction (avertissement uniquement)
# La sécurité réelle est gérée par le sandbox d'exécution (Docker, subprocess)
DANGEROUS_PATTERNS: list[str] = [
    "os.system",
    "subprocess.",
    "eval(",
    "exec(",
    "__import__",
]


def log_dangerous_patterns(code: str, context: str = "") -> list[str]:
    """Alerte si le code extrait contient des patterns dangereux.

    Vérification **soft** — elle ne bloque pas l'exécution (l'isolation
    dans DockerSandbox / SubprocessExecutor s'en charge). Sert uniquement
    à alerter les développeurs pendant le débogage.
    """
    found = [kw for kw in DANGEROUS_PATTERNS if kw.lower() in code.lower()]
    if found:
        tag = f" [{context}]" if context else ""
        logger.warning("Code contains dangerous patterns%s: %s", tag, found)
    return found


class ExtractedFile(BaseModel):
    """Fichier unique validé : nom, contenu, langage, et réparation par langage.

    Le validateur ``content`` applique ``fix_code_by_language()`` qui dispatche
    vers le bon réparateur (Python → compile(), JS → strip types, etc.).
    Le champ ``language`` est déduit automatiquement de l'extension.
    """

    name: str = Field(..., description="Nom du fichier avec extension")
    content: str = Field(..., description="Contenu du fichier")
    language: str = Field(default="", description="Langage détecté (python, javascript, …)")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Vérifie que le nom a une extension supportée et des caractères sûrs."""
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
    def infer_language(self) -> ExtractedFile:
        """Déduit le langage à partir de l'extension du fichier."""
        ext = self.name.lower().split(".")[-1] if "." in self.name else ""
        lang_map = {
            "py": "python", "pyw": "python",
            "js": "javascript", "mjs": "javascript", "cjs": "javascript",
            "ts": "typescript", "mts": "typescript", "cts": "typescript",
            "jsx": "jsx", "tsx": "tsx",
            "sh": "shell", "bash": "shell", "zsh": "shell",
            "ps1": "powershell", "psm1": "powershell", "psd1": "powershell",
            "bat": "batch", "cmd": "batch",
            "rs": "rust", "go": "go", "java": "java",
            "rb": "ruby", "php": "php", "swift": "swift",
            "kt": "kotlin", "scala": "scala",
            "c": "c", "cpp": "cpp", "h": "c", "hpp": "cpp",
            "cs": "csharp", "fs": "fsharp",
            "r": "r", "lua": "lua", "pl": "perl",
            "sql": "sql", "html": "html", "css": "css",
            "json": "json", "yaml": "yaml", "yml": "yaml",
            "toml": "toml", "xml": "xml", "md": "markdown",
        }
        self.language = lang_map.get(ext, ext)
        return self

    @model_validator(mode="after")
    def validate_content(self) -> ExtractedFile:
        """Validate content — apply ``fix_code_by_language()`` for all languages."""
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

        from .repair import fix_code_by_language as _fix_by_lang

        # Apply language-specific repair
        repaired = _fix_by_lang(self.name, stripped)

        # For Python, re-validate with compile() after repair
        if any(self.name.endswith(ext) for ext in _PYTHON_EXTENSIONS):
            try:
                compile(repaired, self.name, "exec")
                self.content = repaired
                return self
            except SyntaxError as e:
                logger.warning(
                    "Syntax error in generated code: %s at line %s",
                    e.msg,
                    e.lineno,
                )
                raise ValueError(f"Invalid Python syntax in '{self.name}': {e}")

        self.content = repaired
        return self


class ExtractedCode(BaseModel):
    """Résultat d'extraction validé : dictionnaire ``{nom_fichier: contenu}``.

    Chaque fichier est instancié comme ``ExtractedFile``, ce qui déclenche
    la validation complète (nom + contenu + compilation Python).
    """

    files: dict[str, str] = Field(..., description="Mapping nom de fichier → contenu")

    @model_validator(mode="after")
    def validate_files(self) -> ExtractedCode:
        """Valide que tous les fichiers ont un nom et un contenu corrects."""
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
