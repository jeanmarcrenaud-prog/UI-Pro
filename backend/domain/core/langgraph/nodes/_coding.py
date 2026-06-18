"""Coding node — the heaviest LangGraph pipeline node.

Extracted from the monolithic ``nodes.py`` to isolate the ~180 lines of
prompt construction, code extraction, and stdlib-shim logic.
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


@_timed_node("coding")
async def coding_node(state: AgentState) -> dict[str, Any]:
    _step_start(state, "coding")
    _emit_step("coding", "Generation du code...")

    # Per-node routing: code generation is the heaviest LLM task. Small
    # models (1.2B) ignore explicit constraints (e.g. "stdlib only") and
    # hallucinate API endpoints/keys. Force the preset's "reasoning"
    # slot (9B+) when node_routing_enabled; otherwise user_model wins.
    llm = _build_llm(state, "reasoning")

    user_message = _get_user_message(state)
    plan_clean = _clean_plan(state.get("plan", {}))
    attempt = state.get("attempt", 0)
    previous_error = state.get("error") or (state.get("execution_result") or {}).get("error")

    # Detect language from user request
    language = _detect_language(user_message)
    state["language"] = language
    lang_cfg = _get_lang_config(language)
    ext = lang_cfg["ext"]
    block = lang_cfg["block"]
    lang_name = lang_cfg["name"]

    # ── Prompt construction ─────────────────────────────────────────────
    # Order matters: system prompt (static) first, then context, then
    # dynamic appendices (examples, quality rules).

    prompt_parts = [
        CODING_SYSTEM_PROMPT,
        f"## Langage cible : {lang_name}",
        f"User request: {user_message}",
    ]

    if plan_clean:
        prompt_parts.append(f"Implementation plan: {json.dumps(plan_clean, ensure_ascii=False)}")

    # Retry path: when attempt > 0, build a structured self-correction
    # prompt that hands the model the previous code, the execution
    # error, and the review issues/suggestions.
    is_fix_attempt = attempt > 0 and bool(previous_error or state.get("review"))
    if is_fix_attempt:
        fix_ctx = format_fix_prompt(
            state, advanced=bool(getattr(settings, "advanced_self_critique", False))
        )
        if fix_ctx:
            prompt_parts.append(fix_ctx)
            logger.info(
                "[coding_node] fix attempt %d/%d — advanced=%s",
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

    # Constraint reinforcement: if the user explicitly forbids `requests` /
    # `httpx` (e.g. "stdlib only", "no requests", "urllib only"), the model
    # is shown to ignore the rule. This block is a "negative example + good
    # example" pair to push it the right way.
    user_msg_lower = user_message.lower()
    stdlib_only_hint = any(
        phrase in user_msg_lower
        for phrase in (
            "stdlib only",
            "no requests",
            "no httpx",
            "urllib only",
            "urllib.request",
            "standard library only",
            "stdlib uniquement",
            "pas de requests",
        )
    )
    if language == "python" and stdlib_only_hint:
        prompt_parts.append(
            "IMPORTANT — STDLIB ONLY (user requirement):\n"
            "The user explicitly asked for stdlib-only code. You MUST use "
            "`urllib.request` for HTTP, NOT `requests` or `httpx`.\n\n"
            "BAD (do NOT do this):\n"
            "```python\n"
            "import requests\n"
            "response = requests.get(url, params=params)\n"
            "data = response.json()\n"
            "```\n\n"
            "GOOD (do this — combines ALL the CODE QUALITY rules above):\n"
            "```python\n"
            "import urllib.request\n"
            "import urllib.parse\n"
            "import json\n"
            "import sys\n"
            "\n"
            "def fetch(url, params=None, timeout=10):\n"
            "    if params:\n"
            "        url = url + ('&' if '?' in url else '?') + urllib.parse.urlencode(params)\n"
            "    try:\n"
            "        with urllib.request.urlopen(url, timeout=timeout) as resp:\n"
            "            return json.loads(resp.read().decode('utf-8'))\n"
            "    except urllib.error.URLError as e:\n"
            "        print(f'Network error: {e.reason}', file=sys.stderr)\n"
            "        raise\n"
            "    except urllib.error.HTTPError as e:\n"
            "        print(f'Server error: HTTP {e.code}', file=sys.stderr)\n"
            "        raise\n"
            "    except json.JSONDecodeError as e:\n"
            "        print(f'Invalid response format: {e}', file=sys.stderr)\n"
            "        raise\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    data = fetch('https://api.example.com/v1/forecast', params={'q': 'x'})\n"
            "    print(data)\n"
            "```\n\n"
            "Note: the GOOD example above uses `urllib.request` (stdlib), has an "
            "explicit `timeout`, a `with` block, three distinct except branches, "
            "and an `if __name__ == '__main__':` guard. Replicate this structure."
        )

    prompt = "\n\n".join(prompt_parts)
    retry_temperature = 0.25 if is_fix_attempt else 0.3
    try:
        full_response = await _llm_run_node(
            llm, prompt, "coding", model_type="fast", temperature=retry_temperature,
        )
    except (asyncio.TimeoutError, TimeoutError) as exc:
        logger.warning("[coding_node] LLM call timed out after %ss — empty fallback", settings.llm_timeout)
        _emit_step("coding", f"⏱️ LLM timeout ({settings.llm_timeout}s)")
        state["code"] = {"files": {}}
        state["error"] = f"LLM code generation timed out after {settings.llm_timeout}s"
        return _step_done(state, "coding", status="error") | {
            "code": state.get("code"),
            "error": state.get("error"),
        }

    _emit_step("coding", "Extraction et validation du code...")
    from ..code_extractor import extract_code_dict
    from ..code_sanitizer import sanitize_files

    state["code"] = extract_code_dict(full_response)

    # Language enforcement: rename files with wrong extension to match
    # the detected language. Small models often ignore the format
    # instruction and output TypeScript/JavaScript when Python was
    # requested, which breaks the executor chain.
    code_files = state["code"].get("files", {})
    wrong_ext = (".ts", ".js", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h", ".rs", ".go")
    renamed: dict[str, str] = {}
    for fname in list(code_files.keys()):
        if fname.endswith(wrong_ext) and not fname.endswith(ext):
            new_fname = fname.rsplit(".", 1)[0] + "." + ext
            code_files[new_fname] = code_files.pop(fname)
            renamed[fname] = new_fname
            logger.info("[coding_node] Renamed %s → %s (language enforcement)", fname, new_fname)
    if renamed:
        state["code"]["files"] = code_files
        state["code"]["_renamed"] = renamed

    # Runtime safety net: Python-specific stdlib shim injection.
    # Detects `requests`/`httpx` imports and prepends urllib-backed shims.
    if language == "python":
        original_files = state["code"].get("files", {})
        sanitized_files, sanitize_meta = sanitize_files(original_files)
        state["code"]["files"] = sanitized_files
        state["code"]["sanitize_meta"] = sanitize_meta

        for inj in sanitize_meta.get("injections", []):
            logger.info(
                "[coding_node] Injected stdlib shim for '%s' in %s "
                "(user requested stdlib-only; model ignored)",
                inj["package"],
                inj["file"],
            )

    files_count = len(state["code"].get("files", {}))
    _emit_step("coding", f"Code généré: {files_count} fichiers")
    state["files_generated"] = dict(state["code"].get("files", {}))
    return _step_done(state, "coding") | {
        "code": state.get("code"),
        "files_generated": state.get("files_generated"),
    }
