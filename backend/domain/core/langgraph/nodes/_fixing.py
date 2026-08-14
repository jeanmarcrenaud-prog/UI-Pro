"""Fixing node — dedicated auto-fix correction step.

Extracted from ``coding_node`` so code generation and self-correction are
separate pipeline steps with their own metrics and step tracking.

The fix loop is::

    execute → should_continue → fixing → review → execute → should_continue → end

``fixing_node`` produces the corrected code (LLM + extraction + sanitize)
and routes to ``review``; ``coding_node`` is now pure generation.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from backend.domain.settings import settings

from ..fix_prompts import format_fix_prompt
from ..prompts import CODING_SYSTEM_PROMPT
from ..state import AgentState

from ._base import (
    _build_code_quality_section,
    _build_llm,
    _build_syntax_example,
    _clean_plan,
    _detect_language,
    _emit_step,
    _get_lang_config,
    _get_user_message,
    _llm_run_node,
    _step_done,
    _step_start,
    _timed_node,
)

logger = logging.getLogger(__name__)


@_timed_node("fixing")
async def fixing_node(state: AgentState) -> dict[str, Any]:
    updates = _step_start(state, "fixing")
    _emit_step("fixing", "Correction automatique du code...")

    # Per-node routing: correction needs the same reasoning tier as code
    # generation — small models ignore the fix context and re-hallucinate.
    llm = _build_llm(state, "reasoning")

    user_message = _get_user_message(state)
    plan_clean = _clean_plan(state.get("plan", {}))
    attempt = state.get("attempt", 0)

    # Detect language from user request
    language = _detect_language(user_message)
    updates["language"] = language
    lang_cfg = _get_lang_config(language)
    ext = lang_cfg["ext"]
    block = lang_cfg["block"]
    lang_name = lang_cfg["name"]
    logger.info("[fixing_node] Langue detectee: %s (ext=.%s, block=%s)", language, ext, block)

    # ── Prompt construction ─────────────────────────────────────────────
    # Order matters: system prompt (static) first, then context, then the
    # fix context (previous code + error + review), then dynamic
    # appendices (syntax rules, quality rules).
    prompt_parts = [
        CODING_SYSTEM_PROMPT,
        f"## Langage cible : {lang_name}",
        f"User request: {user_message}",
    ]

    if plan_clean:
        prompt_parts.append(f"Implementation plan: {json.dumps(plan_clean, ensure_ascii=False)}")

    # Core of the fix: hand the model the previous code, the execution
    # error, and the review issues/suggestions.
    fix_ctx = format_fix_prompt(
        state, advanced=bool(getattr(settings, "advanced_self_critique", False))
    )
    if fix_ctx:
        prompt_parts.append(fix_ctx)
        logger.info(
            "[fixing_node] fix attempt %d/%d — advanced=%s",
            attempt,
            state.get("max_attempts", 3),
            settings.advanced_self_critique,
        )

    # ── Language-specific constraints (reinforce / override) ─────────────
    lang_specific = ""
    if language == "javascript":
        lang_specific = (
            "- N'utilise JAMAIS TypeScript ni d'annotations de type "
            "(`: string`, `: number`, `Promise<...>`, `<T>`, etc.).\n"
        )
    elif language == "python":
        lang_specific = (
            "- Utilise type hints UNIQUEMENT si l'utilisateur le demande.\n"
        )

    # ── Syntax validation examples (per language) ───────────────────────
    syntax_section = (
        "**3. Syntaxe — règle la PLUS importante**\n"
        "- Construis fonction par fonction — ne colle PAS de gros blocs d'un coup.\n"
        "- Chaque `(` DOIT avoir une `)` correspondante, chaque `{` un `}`, chaque `[` un `]`.\n"
        "- Toute chaîne (simple, double, triple-quote) DOIT être correctement fermée.\n"
        "- Tout bloc DOIT avoir un corps en dessous avec une indentation correcte.\n"
        "- AVANT d'écrire, vérifie mentalement que la syntaxe est valide.\n\n"
    )

    # ── Compose final prompt ────────────────────────────────────────────
    prompt_parts.append(
        f"{lang_specific}"
        f"{syntax_section}"
        "MAUVAIS — syntaxe INVALIDE (parenthèse manquante, chaîne non fermée, corps manquant) :\n"
        f"```{block}\n"
        "def fetch(url\n"
        "    return urlopen(url)\n"
        f"```\n"
        f"```{block}\n"
        "print('hello\n"
        "print('world')\n"
        f"```\n\n"
        "BON — syntaxe valide :\n"
        f"```{block}\n"
        f"{_build_syntax_example(language)}\n"
        f"```\n\n"
        f"{_build_code_quality_section(language)}"
    )

    prompt = "\n\n".join(prompt_parts)
    try:
        full_response = await _llm_run_node(
            llm, prompt, "fixing", model_type="fast", temperature=0.25,
        )
    except (asyncio.TimeoutError, TimeoutError) as exc:
        logger.warning("[fixing_node] LLM call timed out after %ss — empty fallback", settings.llm_timeout)
        _emit_step("fixing", f"⏱️ LLM timeout ({settings.llm_timeout}s)")
        updates["code"] = {"files": {}}
        updates["error"] = f"LLM code correction timed out after {settings.llm_timeout}s"
        return _step_done("fixing", updates["steps_history"], status="error") | {
            "code": updates["code"],
            "error": updates["error"],
            "language": updates["language"],
        }

    _emit_step("fixing", "Extraction et validation du code corrigé...")
    from ..code_extractor import extract_code_dict
    from ..code_sanitizer import sanitize_files

    code_data = extract_code_dict(full_response)
    updates["code"] = code_data

    # Language enforcement: rename files with wrong extension to match
    # the detected language. Small models often ignore the format
    # instruction and output TypeScript/JavaScript when Python was
    # requested, which breaks the executor chain.
    code_files = code_data.get("files", {})
    wrong_ext = (".ts", ".js", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h", ".rs", ".go")
    renamed: dict[str, str] = {}
    for fname in list(code_files.keys()):
        if fname.endswith(wrong_ext) and not fname.endswith(ext):
            new_fname = fname.rsplit(".", 1)[0] + "." + ext
            code_files[new_fname] = code_files.pop(fname)
            renamed[fname] = new_fname
            logger.info("[fixing_node] Renamed %s → %s (language enforcement)", fname, new_fname)
    if renamed:
        code_data["files"] = code_files
        code_data["_renamed"] = renamed

    # Runtime safety net: Python-specific stdlib shim injection.
    # Detects `requests`/`httpx` imports and prepends urllib-backed shims.
    if language == "python":
        original_files = code_data.get("files", {})
        sanitized_files, sanitize_meta = sanitize_files(original_files)
        code_data["files"] = sanitized_files
        code_data["sanitize_meta"] = sanitize_meta

        for inj in sanitize_meta.get("injections", []):
            logger.info(
                "[fixing_node] Injected stdlib shim for '%s' in %s "
                "(user requested stdlib-only; model ignored)",
                inj["package"],
                inj["file"],
            )

    files_count = len(code_data.get("files", {}))
    _emit_step("fixing", f"Code corrigé: {files_count} fichiers")
    updates["files_generated"] = dict(code_data.get("files", {}))
    return _step_done("fixing", updates["steps_history"]) | {
        "code": updates["code"],
        "files_generated": updates["files_generated"],
        "language": updates["language"],
    }