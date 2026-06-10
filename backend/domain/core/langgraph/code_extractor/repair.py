"""
code_extractor/repair.py — Utilitaires de réparation pour les erreurs de syntaxe des LLM.

Les LLM produisent parfois du code avec :
- Des parenthèses/crochets/accolades en excès ou manquants
- Une indentation inconsistante (mélange tabulations/espaces, lignes désalignées)

Ce module fournit deux fonctions correctives utilisées par la chaîne de
validation d'``ExtractedFile`` et par la phase de salvage dans ``_finalize``.
"""

from __future__ import annotations

import io
import logging
import textwrap
import tokenize

logger = logging.getLogger(__name__)

_PAIRS: dict[str, str] = {"(": ")", "[": "]", "{": "}"}
_CLOSING = frozenset(_PAIRS.values())


def fix_syntax_errors(code: str) -> str:
    """Tente une réparation basique de la syntaxe pour les erreurs LLM courantes.

    Utilise ``tokenize`` (stdlib) pour ignorer les délimiteurs contenus dans
    les chaînes de caractères et les commentaires — contrairement à une
    approche naïve caractère par caractère.

    Stratégie (2 phases) :

    Phase 1 — Tokenize
        Parcourt les tokens valides, ne conserve que les ``OP`` (opérateurs)
        qui sont des parenthèses/crochets/accolades. Les ``STRING``,
        ``COMMENT`` et autres sont ignorés. Ajoute les fermants manquants
        à la fin du code sans jamais supprimer de caractères.

    Phase 2 — Fallback caractère par caractère
        Si ``tokenize`` échoue (input trop garbled), on tombe dans
        l'algorithme historique qui scanne caractère par caractère avec
        validation ``compile()`` à chaque itération.

    Returns
    -------
        Code réparé (meilleur effort) ou l'original si aucune réparation
        n'est nécessaire ou possible.
    """
    stripped = code.strip()
    if not stripped:
        return code

    # Quick check : déjà valide ?
    try:
        compile(stripped, "<string>", "exec")
        return code
    except SyntaxError:
        pass

    # ── Phase 1 : tokenize-aware ──────────────────────────────────────
    candidate = _repair_with_tokenize(stripped)
    if candidate is not None:
        return candidate

    # ── Phase 2 : fallback caractère par caractère ────────────────────
    _stripped = stripped
    for _ in range(3):
        stack: list[str] = []
        cleaned: list[str] = []
        for ch in _stripped:
            if ch in _PAIRS:
                stack.append(ch)
                cleaned.append(ch)
            elif ch in _CLOSING:
                if stack and _PAIRS.get(stack[-1]) == ch:
                    stack.pop()
                    cleaned.append(ch)
                # else: extra closer → retiré (on tente un salvage)
            else:
                cleaned.append(ch)

        candidate_str = "".join(cleaned)
        if candidate_str == _stripped and stack:
            extra = "".join(_PAIRS[o] for o in reversed(stack))
            candidate_str = _stripped + extra

        try:
            compile(candidate_str, "<string>", "exec")
            if candidate_str != code:
                logger.info("fix_syntax_errors (fallback): code réparé")
            return candidate_str
        except SyntaxError:
            _stripped = candidate_str
            continue

    return code  # Toutes les tentatives ont échoué


def _repair_with_tokenize(stripped: str) -> str | None:
    """Phase 1 : utilise ``tokenize`` pour un bracket matching context-aware.

    Ne compte que les tokens de type ``OP`` (parenthèses, crochets…), en
    ignorant les ``STRING``, ``COMMENT``, etc. Ajoute les fermants manquants
    à la fin sans jamais retirer de caractères.

    Retourne le code réparé, ou ``None`` si ``tokenize`` échoue sur l'input.
    """
    try:
        tokens = tokenize.generate_tokens(io.StringIO(stripped).readline)
    except tokenize.TokenError:
        return None  # Input trop garbled → fallback

    stack: list[str] = []
    # Position du dernier token OP qui a ouvert un bracket non fermé
    # (ligne, colonne) — pour insérer le fermant au plus près du défaut
    last_unmatched_lineno: int | None = None
    last_unmatched_col: int | None = None

    try:
        for tok_type, tok_str, start, end, *_ in tokens:
            if tok_type == tokenize.OP:
                if tok_str in _PAIRS:
                    stack.append(tok_str)
                    last_unmatched_lineno, last_unmatched_col = end
                elif tok_str in _CLOSING:
                    if stack and _PAIRS.get(stack[-1]) == tok_str:
                        stack.pop()
                        # Restaurer la position du nouveau dernier non fermé
                        if stack:
                            pass  # On garde la dernière position connue
                        else:
                            last_unmatched_lineno = None
                            last_unmatched_col = None
                    # Extra closer dans le code → on le garde, pas de suppression
    except tokenize.TokenError:
        # EOF dans une structure imbriquée (ex: ``[`` jamais fermé).
        # Le stack partiel est exploitable — on continue.
        pass

    if not stack:
        return None  # Déjà équilibré (mais peut-être une autre erreur)

    extra = "".join(_PAIRS[o] for o in reversed(stack))

    # Insertion au plus près du défaut si on a la position
    if last_unmatched_lineno is not None and last_unmatched_col is not None:
        candidate = _insert_at_line_end(
            stripped, extra, last_unmatched_lineno, last_unmatched_col
        )
        try:
            compile(candidate, "<string>", "exec")
            logger.info(
                "fix_syntax_errors: inserted %d closer(s) at line %d col %d",
                len(stack),
                last_unmatched_lineno,
                last_unmatched_col,
            )
            return candidate
        except SyntaxError:
            pass

    # Ajout à la fin du fichier
    for sep in ("\n", ""):
        candidate = stripped + sep + extra
        try:
            compile(candidate, "<string>", "exec")
            logger.info(
                "fix_syntax_errors: appended %d closer(s) at end of file",
                len(stack),
            )
            return candidate
        except SyntaxError:
            continue

    # Si on a plusieurs fermants manquants, tenter par sous-ensemble
    if len(stack) > 1:
        for i in range(len(stack) - 1, 0, -1):
            sub_extra = "".join(_PAIRS[o] for o in reversed(stack[:i]))
            for sep in ("\n", ""):
                candidate = stripped + sep + sub_extra
                try:
                    compile(candidate, "<string>", "exec")
                    logger.info(
                        "fix_syntax_errors: appended %d closer(s) (subset) at end of file",
                        i,
                    )
                    return candidate
                except SyntaxError:
                    continue

    return None


def _insert_at_line_end(
    text: str, closer: str, lineno: int, col: int
) -> str:
    """Insère ``closer`` à la fin de la ligne ``lineno`` (1-indexed).

    Cas classique ::

        x = [1, 2,         ← ligne 1
            print(")")]    ← la ligne 2 a déjà son propre ``]``
                            → on insère à la fin de la ligne 1

    Si ``lineno`` dépasse le nombre de lignes, on append à la fin.
    """
    lines = text.split("\n")
    idx = lineno - 1  # 0-indexed
    if 0 <= idx < len(lines):
        lines[idx] = lines[idx] + closer
        return "\n".join(lines)
    return text + closer


def fix_indentation(code: str) -> str:
    """Normalise une indentation inconsistante.

    Stratégie : remonte les lignes sous l'indentation minimum non nulle,
    puis dé-dente tout à la colonne 0. Les tabulations sont converties
    en 4 espaces avant le calcul (comme dans ``_normalize_block_indent``).

    Exemple typique de code LLM mal indenté ::

        import requests       ← outlier (indent 0, devrait être 4)
        import json           ← ok (indent 4)
        from datetime import... ← ok (indent 4)
        url = "..."           ← ok (indent 4)
        params = {            ← ok (indent 4)
            "key": "val"      ← indent plus profonde (8) — préservée après dedent

    Deux stratégies sont essayées :
    1. Remonter les lignes < base_indent → base_indent, puis ``textwrap.dedent``
    2. ``textwrap.dedent`` simple
    La première qui compile est retournée.
    """
    lines = code.expandtabs(4).split("\n")
    non_empty = [l for l in lines if l.strip()]
    if len(non_empty) < 2:
        return code

    indents = [len(l) - len(l.lstrip()) for l in non_empty]
    nonzero = [i for i in indents if i > 0]
    if not nonzero:
        return code

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
        dedented = textwrap.dedent(uniform)
        if dedented != uniform:
            candidates.append(dedented)
        candidates.append(uniform)

    # Strategy 2: simple textwrap.dedent
    dedented_full = textwrap.dedent("\n".join(lines))
    if dedented_full != code:
        candidates.append(dedented_full)

    # Try each candidate, return first that compiles
    for candidate in candidates:
        try:
            compile(candidate, "<string>", "exec")
            logger.info("fix_indentation: code réparé")
            return candidate
        except SyntaxError:
            continue

    return code
