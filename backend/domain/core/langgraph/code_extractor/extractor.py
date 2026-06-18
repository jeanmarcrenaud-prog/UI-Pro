"""
code_extractor/extractor.py — Extraction multi-stratégie de code depuis la sortie brute d'un LLM.

Le LLM peut répondre avec du code dans plusieurs formats : blocs ```python,
```json, JSON pur, ou simplement du code nu. Cette fonction essaie 7 stratégies
séquentielles jusqu'à en trouver une qui produit un dictionnaire ``{files: {}}``
valide.

Chaîne de traitement
--------------------
1. Nettoyage du préambule LLM (``_strip_llm_preamble``)
2. 7 stratégies de parsing (voir ``extract_code_dict``)
3. Validation finale via ``ExtractedCode`` + chaîne de réparation (salvage)
"""

from __future__ import annotations

import json
import logging
import re
import textwrap
from typing import Any

from .models import ExtractedCode, ExtractedFile, _PYTHON_EXTENSIONS
from .repair import fix_indentation, fix_syntax_errors

logger = logging.getLogger(__name__)

# Mapping langage → extension pour les blocs de code génériques (stratégie 2)
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

# Phrases de préambule fréquentes des LLM — on les ignore en début de réponse.
# Inclut l'anglais ("Thinking", "Here's") et le français ("Voici", "Je vais",
# "Analyse") car le LLM peut produire les deux.
_LLM_PREAMBLE_PATTERNS = re.compile(
    r"^(#|//|-\s*)?(Thinking|Analyzing|Reasoning|Here'?s|Here is|Let me|I'?ll|The (solution|code|approach|best)|Code[:\s]|Voici|Je vais|Analyse)",
    re.IGNORECASE,
)


def _strip_llm_preamble(text: str) -> str:
    """Supprime le préambule 'voici le code' ou 'raisonnement' du LLM.

    Parcourt les lignes du début à la recherche du premier bloc de code
    (`` ``` `` ou ``{``), en ignorant les lignes de préambule. Si aucune
    ligne ne correspond à un préambule connu, le texte est retourné intact.
    """
    lines = text.split("\n")
    code_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if _LLM_PREAMBLE_PATTERNS.match(stripped):
            code_start = i + 1
        else:
            # Première ligne non vide qui n'est pas du préambule → début du contenu
            break
    trimmed = "\n".join(lines[code_start:]).strip()
    return trimmed if trimmed else text


def _find_json_objects(text: str) -> list[str]:
    """Trouve les objets JSON racines par comptage d'accolades (respecte les chaînes)."""
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
# Utilitaires partagés par les stratégies 1 (```python) et 2 (générique).
# Fonctions privées — contrat interne à ces deux stratégies uniquement.
# ---------------------------------------------------------------------------


def _normalize_block_indent(block: str) -> str:
    """Supprime l'indentation commune d'un bloc de code.

    Les lignes vides sont conservées (pas supprimées) pour que le nombre
    de lignes corresponde à l'entrée. Les lignes non vides sont dé-dentées
    à l'indentation minimale. Les tabulations sont converties en 4 espaces
    avant le calcul, comme le font les renderers de blocs de code.

    Retourne une chaîne vide si le bloc n'a aucun contenu non vide.
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
    """Génère un nom de fichier unique en cas de collision.

    La première occurrence de ``fname`` est retournée inchangée. Les
    occurrences suivantes reçoivent ``_2``, ``_3``... avant la dernière
    extension (``foo.py`` → ``foo_2.py``). Les noms sans extension
    reçoivent le suffixe en fin de chaîne (``Makefile`` → ``Makefile_2``).

    Le dict ``seen`` est muté sur place — compteur initialisé à 1
    à la première occurrence, incrémenté à chaque collision.
    """
    if fname in seen:
        seen[fname] += 1
        dot_idx = fname.rfind(".")
        if dot_idx != -1:
            return f"{fname[:dot_idx]}_{seen[fname]}{fname[dot_idx:]}"
        return f"{fname}_{seen[fname]}"
    seen[fname] = 1
    return fname


def _validate_block(name: str, content: str, strict: bool = False) -> str:
    """Valide un bloc via ``ExtractedFile`` ; retourne le meilleur contenu possible.

    Délègue à ``ExtractedFile`` qui :
    - Vérifie le nom (extension supportée, caractères sûrs)
    - Compile les fichiers Python (``.py``/``.pyw``) avec chaîne de réparation
    - Passe les autres extensions sans compile

    En cas d'échec de validation :
    - Mode **strict** (``strict=True``) → ``textwrap.dedent`` pour tenter
      un salvage même sur un nom invalide (utilisé par la stratégie 1)
    - Mode **normal** (``strict=False``) → avertit et retourne le contenu brut
      (utilisé par la stratégie 2)

    Le résultat n'est jamais None — l'appelant vérifie ``.strip()``.
    """
    try:
        return ExtractedFile(name=name, content=content).content
    except ValueError:
        if strict:
            return textwrap.dedent(content).strip()
        logger.warning("Block '%s' failed validation: keeping raw", name)
        return content


def extract_code_dict(response: str) -> dict[str, Any]:
    """Extraction multi-stratégie de ``{files: {"nom.py": "code"}}`` depuis une réponse LLM brute.

    Les 7 stratégies sont tentées **séquentiellement** — la première qui
    produit un résultat valide est retournée immédiatement :

    ====== ========================================= ==================
    Strat  Méthode                                  Format cible
    ====== ========================================= ==================
      1    Blocs ```python avec nom de fichier      ``fichier.py``
      2    Blocs ```<lang> génériques               ``script.ps1``, etc.
      3    Blocs ```json                            JSON ``{files: {}}``
      4    Parsing JSON direct de la réponse        JSON ``{files: {}}``
      5    Objet JSON avec clé "files"              JSON ``{files: {}}``
      6    Détection de code Python nu              ``main.py``
      7    *Fallback* — réponse brute en ``main.py`` ``main.py``
    ====== ========================================= ==================

    Returns
    -------
    dict
        Dictionnaire avec la clé ``"files"`` mappant les noms aux codes.
        Contient toujours une clé ``"steps"`` (liste vide par défaut).
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

    # Phase 1 — Stratégies basées sur les blocs ``` (backticks nécessaires)
    for strategy in (
        _strategy_python_blocks,
        _strategy_generic_blocks,
    ):
        if (code_dict := strategy(response_clean)) is not None:
            break

    if code_dict is None:
        # Nettoyage des backticks pour les stratégies JSON et texte brut
        text_no_backticks = re.sub(
            r"^```(?:json|python)?\s*", "", response_clean, flags=re.MULTILINE
        )
        text_no_backticks = re.sub(r"\s*```$", "", text_no_backticks)
        text_no_backticks = text_no_backticks.strip()

        # Phase 2 — Stratégies JSON / texte brut
        for strategy in (
            _strategy_json_blocks,
            _strategy_direct_json,
            _strategy_brace_json,
            _strategy_pure_python,
        ):
            if (code_dict := strategy(text_no_backticks)) is not None:
                break

    # Fallback (stratégie 7) — réponse brute
    if code_dict is None:
        code_dict = {"steps": [], "files": {"main.py": response_clean}}
        logger.info("Fallback (stratégie 7): réponse brute en main.py (%d signes)", len(response_clean))

    # Ensure 'steps' key exists for downstream code that expects it
    if "steps" not in code_dict:
        code_dict["steps"] = []

    # Final validation — salvage chain
    return _finalize(code_dict)


def _extract_filename_from_header(text: str, block_start: int) -> str | None:
    """Cherche un en-tête ``## nom_fichier.ext`` avant un bloc de code.

    Parcourt les lignes non vides avant ``block_start`` à la recherche
    d'un pattern ``## nom.ext``, ``# filename: nom.ext`` ou
    ``// nom.ext`` (commentaire JS/TS). Accepte n'importe quelle extension.
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
    """Stratégie 1 : Extrait les blocs ```python avec nom de fichier."""
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
        normalized = _validate_block(fname, normalized, strict=True)

        if normalized.strip():
            files[fname] = normalized + "\n"

    if not files:
        return None
    logger.info("Strategy 1 (```python blocks): %d files extracted", len(files))
    return {"files": files}


def _strategy_generic_blocks(text: str) -> dict[str, Any] | None:
    """Stratégie 2 : Extrait les blocs ```<langage> génériques (non-Python, non-JSON).

    Mappe les identifiants de langage (powershell, bash, js, etc.) vers
    des extensions de fichier. Cherche les en-têtes ``## nom.ext`` avant
    le bloc pour le nommage.
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
            # Détection TS/JSX explicite
            if lang in ("typescript", "ts", "mts"):
                ext = ".ts"
            elif lang in ("tsx",):
                ext = ".tsx"
            elif lang in ("jsx",):
                ext = ".jsx"
            fname = f"script{ext}"
        fname = _dedup_filename(fname, seen_names)

        normalized = _normalize_block_indent(block_content)
        if not normalized:
            continue
        normalized = _validate_block(fname, normalized)

        if normalized.strip():
            files[fname] = normalized + "\n"

    if not files:
        return None
    logger.info("Strategy 2 (generic code blocks): %d file(s) extracted", len(files))
    return {"files": files}


def _strategy_json_blocks(text: str) -> dict[str, Any] | None:
    """Stratégie 3 : Extrait les blocs ```json."""
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
    """Stratégie 4 : Parse JSON direct de la réponse entière."""
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
    """Stratégie 5 : Trouve un objet JSON avec clé ``files`` par comptage d'accolades."""
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
    """Stratégie 6 : Détecte et retourne du code Python nu (sans ```)."""
    py_start = re.match(r"^\s*(?:def\s+\w+|class\s+\w+|import\s+|from\s+)", text)
    if py_start:
        logger.info("Strategy 6 (pure Python detected): main.py")
        return {"files": {"main.py": text}}
    return None


def _finalize(code_dict: dict[str, Any]) -> dict[str, Any]:
    """Validation finale avec chaîne de réparation (salvage).

    Si le dictionnaire complet échoue la validation, on tente 3 palliatifs
    dans l'ordre :

    1. Supprimer les fichiers dont l'extension est invalide.
    2. Appliquer ``fix_code_by_language()`` à chaque fichier selon son extension.
    3. Réparations par langage (bracket balancing générique).

    Si tout échoue, on retourne le dictionnaire brut pour que l'appelant
    décide — plutôt que de tout jeter.
    """
    try:
        extracted = ExtractedCode.model_validate(code_dict)
        return extracted.to_dict()
    except ValueError as e:
        logger.warning("Final validation failed: %s — attempting salvage...", e)

        if "files" in code_dict:
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

            # Salvage: apply fix_code_by_language() to every file based on extension
            from .repair import fix_code_by_language as _fix_by_lang

            salvage_all: dict[str, str] = {}
            for fname, fcontent in code_dict["files"].items():
                if isinstance(fcontent, str):
                    salvage_all[fname] = _fix_by_lang(fname, fcontent)
            if salvage_all:
                try:
                    extracted = ExtractedCode.model_validate({"files": salvage_all})
                    logger.info(
                        "Salvaged via fix_code_by_language: %d files",
                        len(salvage_all),
                    )
                    return extracted.to_dict()
                except ValueError:
                    pass

        logger.warning("All salvage attempts failed — returning raw content")
        return code_dict
