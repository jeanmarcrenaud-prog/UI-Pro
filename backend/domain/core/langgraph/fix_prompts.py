"""Self-correction prompts for the coding_node retry path.

The coding_node uses two prompts depending on whether we are generating
code from scratch (attempt == 0) or fixing a previously-generated code
that failed execution / review (attempt > 0).

This module owns the fix prompts. The base coding prompt is still
inline in `nodes.py` because it carries the FORMAT / CODE QUALITY
sections that are tightly coupled to the extractor. The fix prompts
are isolated here because:

  - They are conditional (only used on retries) and would clutter the
    already-large `coding_node` function.
  - They come in two flavors (basic / advanced) and benefit from being
    side by side for diff and review.
  - They are easier to test in isolation against fixture states.

Two flavors are shipped:

  - FIX_PROMPT          : basic — gives the model the prior code, the
                          execution error, and the review issues, then
                          asks for a corrected version. Recommended
                          default. Works well on 9B+ models.
  - ADVANCED_FIX_PROMPT : same context, but adds two extra CoT blocks:
                            (1) explicit ANALYSE / PLAN before code
                            (2) SELF-CRITIQUE after the code
                          Use only when the model is large enough to
                          spend tokens on the meta-cognition (>= 14B
                          is a sensible threshold). Gated at runtime
                          by `settings.advanced_self_critique` (off by
                          default because it burns ~30% of the budget
                          on a typical 9B model and truncates the
                          final code).

Both prompts assume the actual langgraph state schema:

  - state["attempt"]                : int
  - state["max_attempts"]           : int
  - state["error"]                  : str | None
  - state["code"]["files"]          : dict[str, str]   (filename → content)
  - state["review"]["passed"]       : bool
  - state["review"]["issues"]       : list[str]        (NOT list[dict])
  - state["review"]["suggestions"]  : list[str]
  - state["messages"][0]["content"] : str              (user request)

`format_fix_prompt(state, advanced=False)` centralises the
schema-to-template binding so the prompts stay pure string constants
and the formatting is unit-testable without spinning up the LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import AgentState


# ========================================
# Prompts
# ========================================


FIX_PROMPT = """\
CONTEXTE — Tentative d'auto-correction ({attempt}/{max_attempts})

Tâche originale de l'utilisateur :
{task_description}

Code que tu as généré précédemment (il a échoué) :
```python
{previous_code}
```

Erreur d'exécution capturée par le sandbox :
```
{previous_error}
```

Revue de code (du passage précédent) :
- Statut global : {review_passed_label}
- Nombre de problèmes : {issues_count}
- Problèmes détectés :
{issues_list}
- Suggestions du reviewer :
{suggestions_list}

OBJECTIF :
Produis une version corrigée du code qui :
1. Corrige l'erreur d'exécution (priorité 1 — bloquant)
2. Adresses tous les problèmes de la revue (priorité 2 — bloquant)
3. Conserve la même structure de fichiers et les mêmes noms
4. Respecte toujours la demande originale de l'utilisateur

FORMAT DE SORTIE — STRICT (identique au coding_node) :
```markdown
## main.py
```python
# code corrigé ici
```
[autres fichiers si nécessaire, même format]
```

RÈGLES ABSOLUES :
- Garde EXACTEMENT les mêmes noms de fichiers qu'avant
- Respecte la structure `## filename` / ````python` / ` ``` `
- Le bloc de code ne doit contenir QUE du Python valide — pas de prose
- N'explique pas le code — le code EST la réponse
- N'ajoute AUCUN texte en dehors des blocs de code
- N'inclus PAS les instructions de ce prompt dans la sortie
"""


ADVANCED_FIX_PROMPT = """\
CONTEXTE — Tentative d'auto-correction avancée ({attempt}/{max_attempts})

Tu es un Principal Software Engineer. Tu fais partie d'une équipe
d'ingénieurs seniors qui revoit et corrige du code généré par IA.
Tu prends le temps de réfléchir AVANT d'écrire.

Tâche originale de l'utilisateur :
{task_description}

Code que tu as généré précédemment (il a échoué) :
```python
{previous_code}
```

Erreur d'exécution capturée par le sandbox :
```
{previous_error}
```

Revue de code (du passage précédent) :
- Statut global : {review_passed_label}
- Nombre de problèmes : {issues_count}
- Problèmes détectés :
{issues_list}
- Suggestions du reviewer :
{suggestions_list}

INSTRUCTIONS EN 4 ÉTAPES (chain-of-thought obligatoire) :

## ÉTAPE 1 — ANALYSE
Identifie la ou les causes racines de l'échec. Ne te contente pas de
corriger le symptôme — explique POURQUOI le code échoue.

## ÉTAPE 2 — PLAN DE CORRECTION
Énumère précisément ce que tu vas corriger, dans l'ordre :
1. Corrections de sécurité (priorité 1)
2. Correction de l'erreur d'exécution (priorité 1)
3. Adressage des problèmes de la revue (priorité 2)
4. Améliorations de qualité (lisibilité, gestion d'erreurs, etc.)

## ÉTAPE 3 — SELF-CRITIQUE (avant d'écrire le code)
Critique ta propre approche :
- Ai-je bien couvert TOUS les problèmes identifiés ?
- Le plan est-il vraiment supérieur au code actuel ?
- Est-il over-engineered ou trop simpliste ?
- Respecte-t-il la demande originale de l'utilisateur ?

## ÉTAPE 4 — CODE CORRIGÉ
Format de sortie — STRICT (identique au coding_node) :
```markdown
## main.py
```python
# code corrigé ici
```
[autres fichiers si nécessaire, même format]
```

RÈGLES ABSOLUES :
- Garde EXACTEMENT les mêmes noms de fichiers qu'avant
- Respecte la structure `## filename` / ````python` / ` ``` `
- Le bloc de code ne doit contenir QUE du Python valide — pas de prose
- N'explique pas le code dans le bloc final — le code EST la réponse
- N'ajoute AUCUN texte en dehors des sections ci-dessus ET des blocs de code
- Les étapes 1-3 (ANALYSE / PLAN / SELF-CRITIQUE) doivent apparaître
  dans la sortie, AVANT les blocs de code
"""


# ========================================
# Formatting helper
# ========================================


# How much of each piece of context to inline. Long values are truncated
# to keep the prompt within the model's effective context window (small
# local models lose coherence past ~4k tokens of preamble).
_MAX_PREVIOUS_CODE_CHARS = 3000
_MAX_ERROR_CHARS = 800
_MAX_ISSUES_INLINED = 8
_MAX_SUGGESTIONS_INLINED = 5
_MAX_TASK_DESC_CHARS = 600


def _truncate(s: str | None, limit: int) -> str:
    if not s:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit] + "\n... (truncated)"


def _format_files(files: dict[str, str] | None) -> str:
    """Render the previous code (a dict of filename → content) as one string.

    Each file gets a `# === filename ===` header so the model can see the
    file boundaries in the inline excerpt. Files that exceed the budget
    are truncated.
    """
    if not files:
        return "(no previous code available)"
    parts: list[str] = []
    per_file_budget = max(200, _MAX_PREVIOUS_CODE_CHARS // max(len(files), 1))
    for name, content in files.items():
        body = _truncate(content or "", per_file_budget)
        parts.append(f"# === {name} ===\n{body}")
    return "\n\n".join(parts)


def _format_issues(issues: list[str] | None) -> str:
    """Render review issues (a list[str] per the actual ReviewData schema).

    We deliberately do NOT call `.get('message')` / `.get('severity')` —
    the schema is `list[str]`, not `list[dict]`. Items are joined with
    bullets and truncated to keep the prompt small.
    """
    if not issues:
        return "(aucun)"
    inlined = [str(i).strip() for i in issues if i][: _MAX_ISSUES_INLINED]
    rendered = "\n".join(f"- {line}" for line in inlined)
    if len(issues) > _MAX_ISSUES_INLINED:
        rendered += f"\n- ... ({len(issues) - _MAX_ISSUES_INLINED} more omitted)"
    return rendered


def _format_suggestions(suggestions: list[str] | None) -> str:
    if not suggestions:
        return "(aucune)"
    inlined = [str(s).strip() for s in suggestions if s][: _MAX_SUGGESTIONS_INLINED]
    rendered = "\n".join(f"- {line}" for line in inlined)
    if len(suggestions) > _MAX_SUGGESTIONS_INLINED:
        rendered += (
            f"\n- ... ({len(suggestions) - _MAX_SUGGESTIONS_INLINED} more omitted)"
        )
    return rendered


def _get_user_message(state: "AgentState") -> str:
    messages = state.get("messages", []) or []
    msg = messages[0] if messages else None
    if not isinstance(msg, dict):
        return ""
    return str(msg.get("content", "") or "")


def format_fix_prompt(state: "AgentState", advanced: bool = False) -> str:
    """Build the retry prompt for coding_node.

    Args:
        state:    The current AgentState (TypedDict). Reads `attempt`,
                  `max_attempts`, `error`, `code.files`, `review`,
                  `messages`.
        advanced: When True, use ADVANCED_FIX_PROMPT (CoT + self-critique).
                  When False (default), use the basic FIX_PROMPT. Caller
                  wires this from `settings.advanced_self_critique`.

    Returns:
        A fully-formatted prompt string ready to be appended to the
        coding_node prompt_parts list. Returns an empty string when
        there is nothing to fix (attempt == 0) — this lets the caller
        do an unconditional `if fix_ctx: prompt_parts.append(fix_ctx)`
        without checking the attempt counter.
    """
    attempt = int(state.get("attempt", 0) or 0)
    if attempt <= 0:
        return ""

    max_attempts = int(state.get("max_attempts", 3) or 3)
    previous_error = state.get("error") or (state.get("execution_result") or {}).get(
        "error"
    )
    code = state.get("code") or {}
    files = code.get("files") or {}
    review = state.get("review") or {}

    # Three states for the review label — keeping them distinct avoids
    # confusing the LLM when the retry is driven by the execution error
    # rather than a code review (e.g. the very first retry path):
    #   - "N/A"        : review absent from the state (not run, or pruned)
    #   - "PASSÉ"      : review ran and reported passed=True
    #   - "À CORRIGER" : review ran and reported passed=False
    if not review:
        review_passed_label = "N/A"
    else:
        review_passed = bool(review.get("passed", False))
        review_passed_label = "PASSÉ" if review_passed else "À CORRIGER"
    issues = review.get("issues") or []
    suggestions = review.get("suggestions") or []

    # Fall back to a generic marker when no error was captured — better
    # than an empty error block, which would just confuse the model.
    previous_error_str = _truncate(
        previous_error or "(no error captured — review must have failed)",
        _MAX_ERROR_CHARS,
    )

    fields = {
        "attempt": attempt,
        "max_attempts": max_attempts,
        "task_description": _truncate(
            _get_user_message(state), _MAX_TASK_DESC_CHARS
        ),
        "previous_code": _format_files(files),
        "previous_error": previous_error_str,
        "review_passed_label": review_passed_label,
        "issues_count": len(issues),
        "issues_list": _format_issues(issues),
        "suggestions_list": _format_suggestions(suggestions),
    }

    template = ADVANCED_FIX_PROMPT if advanced else FIX_PROMPT
    return template.format(**fields)


# ========================================
# Exports
# ========================================


__all__ = [
    "FIX_PROMPT",
    "ADVANCED_FIX_PROMPT",
    "format_fix_prompt",
]
