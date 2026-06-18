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

logger = logging.getLogger(__name__)

_PAIRS: dict[str, str] = {"(": ")", "[": "]", "{": "}"}
_CLOSING = frozenset(_PAIRS.values())

# Caractères Unicode problématiques fréquents dans le code généré par LLM
_INVALID_CHAR_REPLACEMENTS: dict[str, str] = {
    "♦": "",
    "●": "",
    "→": "->",
    "⇒": "=>",
    "\u0080": "",
    "\u0099": "'",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
}


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

    if ext in ("py", "pyw"):
        return fix_python_syntax(content)
    elif ext in ("js", "mjs", "cjs"):
        return fix_javascript_syntax(content)
    elif ext in ("ts", "mts", "cts"):
        return fix_typescript_syntax(content)
    elif ext in ("jsx", "tsx"):
        return fix_javascript_syntax(content)
    elif ext in ("sh", "bash", "zsh"):
        return fix_shell_syntax(content)
    elif ext in ("bat", "cmd"):
        return _fix_bracket_balance(content)
    elif ext in ("ps1", "psm1", "psd1"):
        return _fix_bracket_balance(content)
    else:
        return fix_generic_content(content)


# ── Réparateur Python (existant) ─────────────────────────────────────────


def fix_python_syntax(code: str) -> str:
    """Répare la syntaxe Python via indent + bracket balancing + compile().

    Enchaîne ``fix_indentation()`` puis ``fix_syntax_errors()``.
    """
    indented = fix_indentation(code)
    return fix_syntax_errors(indented)


# ── Réparateur JavaScript/JSX ────────────────────────────────────────────


def fix_javascript_syntax(code: str) -> str:
    """Répare les erreurs courantes en JavaScript/JSX.

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
    in_comment = False

    for line in lines:
        stripped = line.strip()

        # Skip comments
        if stripped.startswith("//") or stripped.startswith("#"):
            fixed.append(line)
            continue
        if "/*" in stripped:
            in_comment = True
        if in_comment:
            fixed.append(line)
            if "*/" in stripped:
                in_comment = False
            continue

        original = line

        # 1. Remove generic type params on functions: function foo<T>( → function foo(
        line = re.sub(r"(function\s+\w+)\s*<[^>]+>\s*\(", r"\1(", line)

        # 2. Remove type annotations INSIDE parens (function params).
        #    Order matters: match complex types (array[]) before simple keywords.
        #
        #    2a. Array types: items: string[] → items
        line = re.sub(
            r"(?<=[(,])\s*(\w+)\s*:\s*\w+(?:<[^>]*>)?\[\]",
            r" \1",
            line,
        )

        #    2b. Simple keyword types: city: string, timeout: number
        line = re.sub(
            r"(?<=[(,])\s*(\w+)\s*:\s*(string|number|boolean|any|void|never"
            r"|unknown|null|undefined|bigint|symbol)\b",
            r" \1",
            line,
        )

        #    2c. Complex types inside parens: callback: (item) => void → callback
        #        callback?: (item) => void → callback?
        line = re.sub(
            r"(?<=[(,])\s*(\w+\??)\s*:\s*\([^)]*\)\s*(?:=>|:)\s*\w+(?:<[^>]*>)?",
            r" \1",
            line,
        )

        #    2d. Optional param with type + default: name?: string = 'hello' → name? = 'hello'
        line = re.sub(
            r"(?<=[(,])\s*(\w+\?)\s*:\s*\w+(?:\[\])?\s*(=)",
            r" \1 \2",
            line,
        )

        #    2e. Optional param with type + comma: name?: string, → name?,
        line = re.sub(
            r"(?<=[(,])\s*(\w+\?)\s*:\s*\w+(?:\[\])?(\s*[,)])",
            r" \1\2",
            line,
        )

        # 3. Remove return type between ) and { or ) and => or ) and :
        #    ): Promise<string> { → ) {
        line = re.sub(
            r"(\))\s*:\s*(string|number|boolean|any|void|never|unknown|null"
            r"|undefined|bigint|symbol|Promise\s*<[^>]+>"
            r"|Array\s*<[^>]+>|Record\s*<[^>]+,\s*[^>]+>)\s*",
            r"\1 ",
            line,
        )

        # 4. Arrow return type: (x) => Promise<string> → (x) =>
        line = re.sub(
            r"(\))\s*:\s*(string|number|boolean|any|void|never|unknown|null"
            r"|undefined|bigint|symbol)\s*(=>)",
            r"\1 \3",
            line,
        )

        # 5. Const/let/var type annotations (keep value if present):
        #    const x: string = "hello" → const x = "hello"
        #    But NOT object properties: { signal: AbortSignal }
        #    Strategy: only match after const/let/var on the same line
        line = re.sub(
            r"\b(const|let|var)\s+(\w+)\s*:\s*(string|number|boolean|any|void"
            r"|never|unknown|null|undefined|bigint|symbol"
            r"|Promise\s*<[^>]+>)\s*(=)",
            r"\1 \2 \4",
            line,
        )

        # 6. Class property type annotations: propertyName: string;
        #    But NOT object literal keys: key: value
        #    Conservative: only after visibility modifiers or at line start
        line = re.sub(
            r"^\s*(public|private|protected|readonly|static)\s+(\w+)\s*:\s*"
            r"(string|number|boolean|any|void|never|unknown|null|undefined"
            r"|bigint|symbol)",
            r"\1 \2",
            line,
        )

        if line != original:
            logger.debug("fix_js: %s → %s", original.strip(), line.strip())
        fixed.append(line)

    result = "\n".join(fixed)
    balance_fixed = _fix_bracket_balance(result)
    return balance_fixed.strip()


def fix_typescript_syntax(code: str) -> str:
    """Répare les erreurs courantes en TypeScript.

    Les TS étant déjà valide JS dans la plupart des cas, on conserve
    les annotations. La réparation se concentre sur :
    - L'équilibrage des parenthèses / crochets
    - La dé-dentation
    """
    dedented = textwrap.dedent(code)
    return _fix_bracket_balance(dedented).strip()


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
    balanced = _fix_bracket_balance(dedented)
    # Collapse multiple blank lines
    balanced = re.sub(r"\n{3,}", "\n\n", balanced)
    return balanced.strip()


# ── Bracket balancer générique (indépendant du langage) ────────────────


def _fix_bracket_balance(code: str) -> str:
    """Équilibre les parenthèses/crochets/accolades sans utiliser ``compile()``.

    Version purement syntaxique (indépendante du langage) — contrairement
    à ``fix_syntax_errors`` qui utilise ``tokenize`` + ``compile()`` (Python).
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
    cleaned = _remove_invalid_characters(stripped)
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


def _remove_invalid_characters(code: str) -> str:
    """Supprime les caractères de contrôle et symboles non-ASCII problématiques.

    Les LLM génèrent souvent du code avec des caractères invisibles ou des
    symboles (♦, ●, →, ⇒, guillemets courbes, caractères de contrôle) qui
    causent des ``SyntaxError`` même si le reste du code est correct.

    Exemple réel ::
        print(f"Temp: {weather.temperature} ♦C")   # ♦ invalide en Python
    """
    # Remplacement des symboles problématiques fréquents
    for old, new in _INVALID_CHAR_REPLACEMENTS.items():
        code = code.replace(old, new)

    # Supprimer tout caractère de contrôle restant (sauf \n \t \r)
    code = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", "", code)

    return code


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


def _repair_with_char_fallback(stripped: str) -> str:
    """Phase 2 : fallback caractère par caractère (résilient).

    Parcourt le code caractère par caractère en maintenant un stack de
    brackets ouverts. Retire les fermants surnuméraires (salvage) et ajoute
    les fermants manquants. Valide avec ``compile()`` à chaque itération.
    """
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
            if candidate_str != stripped:
                logger.info("fix_syntax_errors (fallback): code réparé")
            return candidate_str
        except SyntaxError:
            _stripped = candidate_str
            continue

    return stripped  # Toutes les tentatives ont échoué


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
