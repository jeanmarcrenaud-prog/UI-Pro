"""
code_extractor/utils.py — Utilitaires partagés entre extractor, repair et models.

Contient les fonctions et constantes utilisées par plusieurs modules du package,
sans dépendance vers les autres modules du package (pas d'import circulaire).
"""

from __future__ import annotations

import re


# ── Constantes de bracket matching ────────────────────────────────────────

_PAIRS: dict[str, str] = {"(": ")", "[": "]", "{": "}"}
_CLOSING = frozenset(_PAIRS.values())


# ── Caractères Unicode problématiques ─────────────────────────────────────

_INVALID_CHAR_REPLACEMENTS: dict[str, str] = {
    # Symboles décoratifs (LLM aiment les puces et flèches Unicode)
    "♦": "",
    "●": "",
    "•": "",
    "→": "->",
    "➔": "->",
    "⇒": "=>",
    "➜": "->",
    "❯": "->",
    # Caractères de contrôle / invisibles
    "\u0080": "",
    "\u0099": "'",
    # Guillemets typographiques courbes → ASCII
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    # Guillemets typographiques français
    "\u00ab": '"',
    "\u00bb": '"',
}


# ── Nettoyage Unicode ─────────────────────────────────────────────────────

def remove_invalid_characters(code: str) -> str:
    """Supprime les caractères de contrôle et symboles non-ASCII problématiques.

    Les LLM génèrent souvent du code avec des caractères invisibles ou des
    symboles (♦, ●, →, ⇒, guillemets courbes, caractères de contrôle) qui
    causent des ``SyntaxError`` même si le reste du code est correct.
    """
    for old, new in _INVALID_CHAR_REPLACEMENTS.items():
        code = code.replace(old, new)
    # Supprimer tout caractère de contrôle restant (sauf \\n \\t \\r)
    code = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", "", code)
    return code


# ── Bracket balancer générique ────────────────────────────────────────────

def fix_bracket_balance(code: str) -> str:
    """Équilibre les parenthèses/crochets/accolades sans utiliser ``compile()``.

    Version purement syntaxique (indépendante du langage).
    """
    stack: list[str] = []
    cleaned: list[str] = []

    in_single_quote = False
    in_double_quote = False
    in_backtick = False
    i = 0
    while i < len(code):
        ch = code[i]
        prev_ch = code[i - 1] if i > 0 else ""

        # Toggle string state (respect escapes)
        if ch == "'" and not in_double_quote and not in_backtick and prev_ch != "\\":
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote and not in_backtick and prev_ch != "\\":
            in_double_quote = not in_double_quote
        elif ch == "`" and not in_single_quote and not in_double_quote and prev_ch != "\\":
            in_backtick = not in_backtick

        if not in_single_quote and not in_double_quote and not in_backtick:
            if ch in _PAIRS:
                stack.append(ch)
                cleaned.append(ch)
            elif ch in _CLOSING:
                if stack and _PAIRS.get(stack[-1]) == ch:
                    stack.pop()
                    cleaned.append(ch)
                # else: extra closer → ignoré
            else:
                cleaned.append(ch)
        else:
            cleaned.append(ch)
        i += 1

    result = "".join(cleaned)
    if stack:
        result += "".join(_PAIRS[o] for o in reversed(stack))
    return result


# ── Indentation ───────────────────────────────────────────────────────────

def normalize_block_indent(block: str) -> str:
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


# ── Dedup filename ────────────────────────────────────────────────────────

def dedup_filename(fname: str, seen: dict[str, int]) -> str:
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
