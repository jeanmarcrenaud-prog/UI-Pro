"""
code_extractor/repair.py — Utilitaires de réparation pour les erreurs de syntaxe des LLM.

Les LLM produisent parfois du code avec :
- Des parenthèses/crochets/accolades en excès ou manquants
- Une indentation inconsistante (mélange tabulations/espaces, lignes désalignées)
- Des caractères Unicode invalides ou des symboles spéciaux (♦, ●, →, ⇒, guillemets
  typographiques, caractères de contrôle) qui cassent la syntaxe Python
- Des annotations de type TypeScript exécutées comme du JavaScript pur
- Du shell mélangé avec d'autres langages

Ce module fournit des réparateurs spécialisés par langage, dispatchés
automatiquement via ``fix_code_by_language()``.
"""

from __future__ import annotations

import io
import logging
import re
import textwrap
import tokenize

from .utils import (
    _CLOSING,
    _INVALID_CHAR_REPLACEMENTS,
    _PAIRS,
    fix_bracket_balance,
    remove_invalid_characters,
)

logger = logging.getLogger(__name__)


# ── Dispatcher ────────────────────────────────────────────────────────────


def fix_code_by_language(name: str, content: str) -> str:
    """Route vers le bon réparateur selon l'extension du fichier.

    Arguments
    ---------
    name
        Nom du fichier (ex: ``main.py``, ``script.ts``, ``install.sh``).
    content
        Contenu brut du fichier à réparer.

    Returns
    -------
    str
        Contenu réparé (meilleur effort). Si aucune réparation spécifique
        n'est disponible, retourne ``fix_generic_content()``.
    """
    ext = name.lower().split(".")[-1] if "." in name else ""
    lang = ext

    if ext in ("py", "pyw"):
        lang = "python"
        result = fix_python_syntax(content)
    elif ext in ("js", "mjs", "cjs"):
        lang = "javascript"
        result = fix_javascript_syntax(content)
    elif ext in ("ts", "mts", "cts"):
        lang = "typescript"
        result = fix_typescript_syntax(content)
    elif ext in ("jsx", "tsx"):
        lang = "jsx/tsx"
        result = fix_javascript_syntax(content)
    elif ext in ("sh", "bash", "zsh"):
        lang = "shell"
        result = fix_shell_syntax(content)
    elif ext in ("bat", "cmd"):
        lang = "batch"
        result = fix_bracket_balance(content)
    elif ext in ("ps1", "psm1", "psd1"):
        lang = "powershell"
        result = fix_bracket_balance(content)
    else:
        lang = f"{ext} (generic)"
        result = fix_generic_content(content)

    if result != content and len(content) > 50:
        delta = len(result) - len(content)
        logger.info(
            "fix_code_by_language: %s (%s) — %d → %d chars (%+d)",
            name, lang, len(content), len(result), delta,
        )

    return result


# ── Réparateur Python (existant) ─────────────────────────────────────────


def fix_python_syntax(code: str) -> str:
    """Répare la syntaxe Python via indent + bracket balancing + compile().

    Enchaîne ``fix_indentation()`` puis ``fix_syntax_errors()``.
    """
    indented = fix_indentation(code)
    return fix_syntax_errors(indented)


# ── Réparateur JavaScript/JSX ────────────────────────────────────────────


def fix_javascript_syntax(code: str) -> str:
    """Répare les erreurs courantes en JavaScript/JSX/TSX (exécuté comme JS).

    Supprime les annotations de type TypeScript qui cassent Node.js :
    - ``city: string`` dans les paramètres de fonction → ``city``
    - ``): Promise<string>`` → ``)``
    - ``(x: number): string =>`` → ``(x) =>``
    - ``const x: string =`` → ``const x =``

    Préserve les propriétés d'objets (``{ signal: AbortSignal }``) et
    les alias de destructuring (``const { x: alias }``).
    """
    lines = code.split("\n")
    fixed: list[str] = []
    in_block_comment = False

    for line in lines:
        stripped = line.strip()

        # Block comment en cours
        if in_block_comment:
            fixed.append(line)
            if "*/" in stripped:
                in_block_comment = False
            continue

        # Ligne vide, commentaire // ou # → sauter
        if not stripped or stripped.startswith(("//", "#")):
            fixed.append(line)
            continue

        # Début de bloc commentaire /* */
        if "/*" in stripped:
            in_block_comment = True
            fixed.append(line)
            continue

        original = line

        # 1. Supprime les generics <T> sur fonctions: function foo<T>( → function foo(
        line = re.sub(r"(function\s+\w+)\s*<[^>]+>\s*\(", r"\1(", line)

        # 2. Supprime les annotations de type dans les paramètres de fonction.
        #    2a. D'abord les optionnels avec valeur par défaut (pour préserver le =)
        #        name?: string = 'hello' → name? = 'hello'
        line = re.sub(
            r"([(,])\s*(\w+\?)\s*:\s*\w+(?:\[\])?\s*(=)",
            r"\1\2 \3",
            line,
        )
        #    2b. Tous les autres types de paramètres: name: Type → name
        #        Gère aussi les types complexes: callback: (item) => void → callback
        line = re.sub(
            r"([(,])\s*(\w+\??)\s*:\s*(?:[^,()]|\([^)]*\))+\s*(?=[,)])",
            r"\1\2",
            line,
        )

        # 3. Supprime les annotations de type de retour: ): Type { → ) {
        #    Gère aussi ): Type => → ) => et ): Type, → ),
        line = re.sub(r"(\))\s*:\s*[^){]+(\s*[{=])", r"\1\2", line)

        # 4. Supprime les annotations de type const/let/var:
        #    const x: Type = "hello" → const x = "hello"
        #    Ne touche PAS aux propriétés d'objets: { signal: AbortSignal }
        line = re.sub(
            r"\b(const|let|var)\s+(\w+)\s*:\s*[^=]+(\s*=)",
            r"\1 \2\3",
            line,
        )

        # 5. Supprime les annotations de type sur les propriétés de classe:
        #    public name: string; → public name;
        #    Uniquement après modificateur de visibilité
        line = re.sub(
            r"^\s*(public|private|protected|readonly|static)\s+(\w+)\s*:\s*"
            r"[^;=]+(?=\s*[;{])",
            r"\1 \2",
            line,
        )

        # 6. Supprime les types génériques TypeScript inline:
        #    { data: Record<string, any> } → { data }
        #    (ces syntaxes sont TS uniquement et cassent Node)
        line = re.sub(
            r":\s*(Record|Array|Promise|Map|Set|WeakMap|WeakSet|"
            r"Partial|Required|Readonly|Pick|Omit|Exclude|Extract|"
            r"NonNullable|Parameters|ReturnType)\s*<[^>]+>",
            "",
            line,
            flags=re.IGNORECASE,
        )

        if line != original:
            logger.debug("fix_js: %s → %s", original.strip()[:80], line.strip()[:80])
        fixed.append(line)

    result = "\n".join(fixed)
    balance_fixed = fix_bracket_balance(result)
    return balance_fixed.strip()


def fix_typescript_syntax(code: str) -> str:
    """Répare les erreurs courantes en TypeScript.

    TypeScript est un sur-ensemble de JavaScript : on réutilise le réparateur
    JS (qui supprime les annotations de type pour l'exécution Node), puis on
    complète avec bracket balancing.
    """
    # Nettoyage Unicode → JS repair (type stripping) → bracket balance
    cleaned = remove_invalid_characters(code)
    dedented = textwrap.dedent(cleaned)
    js_fixed = fix_javascript_syntax(dedented)
    return fix_bracket_balance(js_fixed).strip()


# ── Réparateur Shell ─────────────────────────────────────────────────────


def fix_shell_syntax(code: str) -> str:
    """Répare les erreurs courantes en Shell/Bash.

    - Supprime les backticks Python/JS qui entourent le code
    - Nettoie les sauts de ligne excédentaires
    - Supprime les annotations type Python en début de ligne
    """
    # Remove surrounding language backticks
    code = re.sub(r"^```\w*\s*", "", code)
    code = re.sub(r"\s*```$", "", code)
    # Remove stray Python-like annotations (def, class, import, print)
    code = re.sub(r"^\s*(def |class |import |from |print\s*\().*$", "", code, flags=re.MULTILINE)
    # Collapse multiple blank lines
    code = re.sub(r"\n{3,}", "\n\n", code)
    return code.strip()


# ── Réparateur générique ─────────────────────────────────────────────────


def fix_generic_content(code: str) -> str:
    """Réparation de base pour tout autre langage.

    - Dé-dentation
    - Équilibrage parenthèses/crochets/accolades
    - Suppression des lignes vides multiples
    """
    dedented = textwrap.dedent(code)
    balanced = fix_bracket_balance(dedented)
    # Collapse multiple blank lines
    balanced = re.sub(r"\n{3,}", "\n\n", balanced)
    return balanced.strip()


def fix_syntax_errors(code: str) -> str:
    """Répare les erreurs de syntaxe LLM : brackets + caractères invalides.

    Stratégie (3 phases) :

    Phase 0 — Nettoyage Unicode
        Supprime les caractères de contrôle et remplace les symboles
        problématiques (♦, ●, →, ⇒, guillemets typographiques) par des
        équivalents sûrs. Cette phase est appliquée en premier car ces
        caractères peuvent empêcher le tokenize de fonctionner correctement.

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

    # Phase 0 — Nettoyage Unicode (appliqué AVANT tout)
    cleaned = remove_invalid_characters(stripped)
    if cleaned != stripped:
        logger.info("fix_syntax_errors: removed invalid unicode characters")

    # Quick check : déjà valide ?
    try:
        compile(cleaned, "<string>", "exec")
        return cleaned
    except SyntaxError:
        pass

    # Phase 1 : tokenize-aware
    candidate = _repair_with_tokenize(cleaned)
    if candidate is not None:
        return candidate

    # Phase 2 : fallback caractère par caractère
    return _repair_with_char_fallback(cleaned)


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
                        if stack:
                            # Après le pop, le dernier unmatched est le fermant
                            # qu'on vient de traiter — on met à jour pour que
                            # les fermants restants soient insérés au bon endroit
                            last_unmatched_lineno, last_unmatched_col = end
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


def _repair_with_char_fallback(stripped: str) -> str:
    """Phase 2 : fallback caractère par caractère (résilient).

    Parcourt le code caractère par caractère en maintenant un stack de
    brackets ouverts. Retire les fermants surnuméraires et ajoute les
    fermants manquants. Valide avec ``compile()`` en une seule passe.

    Contrairement à ``_repair_with_tokenize``, cette version :
    - Ne dépend pas du tokenizer Python (résiste au garbled)
    - Supprime les fermants surnuméraires (``algo(]`` → ``algo()``)
    - Ne tente pas de position intelligente pour les insertions
    """
    stack: list[str] = []
    cleaned: list[str] = []
    for ch in stripped:
        if ch in _PAIRS:
            stack.append(ch)
            cleaned.append(ch)
        elif ch in _CLOSING:
            if stack and _PAIRS.get(stack[-1]) == ch:
                stack.pop()
                cleaned.append(ch)
            # else: fermant surnuméraire → supprimé
        else:
            cleaned.append(ch)

    result = "".join(cleaned)

    # Ajouter les fermants manquants
    if stack:
        extra = "".join(_PAIRS[o] for o in reversed(stack))
        result += extra

    # Validation unique
    if result != stripped:
        try:
            compile(result, "<string>", "exec")
            logger.info("fix_syntax_errors (fallback): code réparé")
            return result
        except SyntaxError:
            pass

    return stripped  # Échec — on rend l'original inchangé


def _insert_at_line_end(
    text: str, closer: str, lineno: int, col: int
) -> str:
    """Insère ``closer`` à la fin de la ligne ``lineno`` (1-indexed).

    Cas classique ::

        x = [1, 2,         ← ligne 1
            print(")"]    ← la ligne 2 a déjà son propre ``]``
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
