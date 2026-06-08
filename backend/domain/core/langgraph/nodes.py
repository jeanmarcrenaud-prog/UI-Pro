"""LangGraph pipeline nodes."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Literal

from backend.domain.settings import settings

from .fix_prompts import format_fix_prompt
from .state import AgentState, CodeData, PlanData, ReviewData

logger = logging.getLogger(__name__)


# ========================================
# Helpers
# ========================================


def _get_user_message(state: AgentState) -> str:
    messages = state.get("messages", [])
    msg = messages[0] if messages else None
    return msg.get("content", "") if msg else ""


def _get_model_info(state: AgentState) -> tuple[str, str]:
    metadata = state.get("metadata", {})
    return (metadata or {}).get("model", ""), (metadata or {}).get("provider", "ollama")


def _clean_plan(plan: PlanData | None) -> dict[str, object]:
    if plan is None:
        return {}
    return {k: v for k, v in plan.items() if k not in ("raw", "thinking", "analysis")}


_llm_router_instance = None


def _get_llm_router():
    global _llm_router_instance
    if _llm_router_instance is None:
        from backend.infrastructure.llm_router import LLMRouter

        _llm_router_instance = LLMRouter()
    return _llm_router_instance


def _emit_step(phase: str, message: str):
    try:
        from backend.domain.core.events import emit_agent_step

        emit_agent_step(phase, message)
    except Exception:
        pass


# Heuristics used by the reviewing_node to surface severity and a
# coarse quality score from a free-text review. Both run in
# microseconds and never block on the LLM — the LLM is asked for a
# score in the prompt (so we prefer it when present) but the
# classifier and the score fallback are deterministic and
# non-LLM-dependent. The keyword lists are intentionally short and
# high-precision: false positives would just clutter format_fix_prompt
# and waste retry context.
_HIGH_SEVERITY_KEYWORDS = (
    "error", "undefined", "nameerror", "typeerror", "syntax",
    "import", "missing", "crash", "exception", "injection",
    "security", "vulnerability", "xss", "csrf", "rce", "ssrf",
    "race", "deadlock", "leak", "secret", "credential",
)
_MEDIUM_SEVERITY_KEYWORDS = (
    "warning", "deprecated", "unused", "no entry-point",
    "no type", "no timeout", "no error", "no try", "no except",
    "no if __name__", "stdlib only", "should", "consider",
)


def _classify_issue_severity(text: str) -> str:
    """Map a free-text review issue to "high" / "medium" / "low".

    Keyword-based heuristic. We pick the highest severity that matches
    (high > medium > low) and return "low" if nothing matches.
    Operates on lowercased text. Defensive against empty / non-str
    input.
    """
    if not isinstance(text, str) or not text:
        return "low"
    t = text.lower()
    for kw in _HIGH_SEVERITY_KEYWORDS:
        if kw in t:
            return "high"
    for kw in _MEDIUM_SEVERITY_KEYWORDS:
        if kw in t:
            return "medium"
    return "low"


def _heuristic_review_score(issues: list[str], suggestions: list[str]) -> float:
    """Coarse 0.0-1.0 quality score from issue / suggestion counts.

    Heuristic: start at 1.0, subtract 0.10 per issue and 0.05 per
    suggestion, clamped to [0.0, 1.0]. The LLM is asked for a
    richer score in the prompt and that wins when present and
    well-formed; this is the deterministic fallback.
    """
    if not isinstance(issues, list):
        issues = []
    if not isinstance(suggestions, list):
        suggestions = []
    score = 1.0 - 0.10 * len(issues) - 0.05 * len(suggestions)
    return max(0.0, min(1.0, score))


# ========================================
# Nodes
# ========================================


def _force_model_for(tier: str) -> str:
    """Resolve the preset tier to a model name, honoring the routing toggle.

    Returns the preset's model for the given tier when per-node routing
    is enabled (the default) AND that model is actually discovered on
    a running backend. Returns "" (empty) when:

      - the user has disabled routing (legacy "all nodes use the chat
        model" path);
      - the preset model is not in the model_discovery cache (e.g.
        model_fast points to a LM Studio model but LM Studio is off).

    In the second case the LLMWrapper takes the legacy user_model path
    on the user's selected backend, which is safe and predictable. The
    alternative — silently forwarding an undiscovered model to whatever
    backend the user happens to be on — produced the
    LLMModelNotFoundError in the original bug report.

    Note on cold cache: if model_discovery hasn't run yet (the cache
    is empty), we keep the preset candidate as best effort. The
    LLMWrapper's own discovery lookup will catch it on first call
    and the router will surface a clean 404 if it's truly missing.
    """
    if not settings.get_node_routing_enabled():
        return ""
    candidate = settings.get_model_for_task(tier)
    if not candidate:
        return ""

    # Late import: model_discovery pulls in heavy backend clients, and
    # we don't want to slow down the import of this module for tests
    # or simple unit paths.
    try:
        from backend.infrastructure.model_discovery import (
            get_model_discovery,
        )
    except Exception:  # pragma: no cover - import-time guard
        return candidate

    try:
        discovered_backend = (
            get_model_discovery().get_backend_for_model(candidate)
        )
    except Exception:
        # Discovery itself failed (e.g. backend process is in a bad
        # state). Best effort: keep the candidate and let the router
        # surface whatever error it actually produces.
        return candidate

    if discovered_backend is None:
        # Warm cache but the model isn't on any running backend.
        # Log once per call so the user can fix their preset in
        # Settings, then return "" -> legacy user_model path.
        logger.warning(
            "[routing] Preset tier '%s' points to model '%s', which is "
            "not discovered on any running backend. Falling back to "
            "the user's chat model. Either start the backend that hosts "
            "this model (check Settings -> Backends), or change the "
            "active preset in Settings -> Models.",
            tier,
            candidate,
        )
        return ""
    return candidate


async def analyzing_node(state: AgentState) -> AgentState:
    _emit_step("analyzing", "Analyse des exigences...")

    user_model, user_provider = _get_model_info(state)
    # Per-node routing: classification is a simple task that benefits from
    # a fast, lightweight model. We force the preset's "fast" slot so a
    # 1.2B classifier isn't asked to do reasoning, and conversely a
    # 35B model isn't wasted on a 30-token JSON output. Honored only
    # when node_routing_enabled is true; otherwise user_model wins.
    force_model = _force_model_for("fast")
    routing_state = "on" if force_model else "off (user model)"
    logger.info(
        f"[analyzing_node] user_model={user_model} → force_model={force_model or user_model} (tier=fast, routing={routing_state})"
    )

    from .llm_wrapper import LLMWrapper

    llm = LLMWrapper(
        _get_llm_router(), user_model, user_provider, force_model=force_model
    )
    user_message = _get_user_message(state)

    _emit_step("analyzing", "Classification de la tâche...")
    # Use angle-bracket placeholders to avoid small models (e.g. 1.2B)
    # misinterpreting "code|reasoning|general" as a literal value. Explicit
    # value list + one-shot example makes the directive unambiguous.
    prompt = (
        f"User request: {user_message}\n\n"
        "Classify the task. Respond with ONLY a valid JSON object:\n"
        '{"task_type": "<code|reasoning|general>", "summary": "<brief description>"}\n\n'
        "Pick ONE task_type value:\n"
        '- "code": user wants code written (script, function, file)\n'
        '- "reasoning": user wants analysis, planning, or explanation\n'
        '- "general": chat, Q&A, or anything else\n\n'
        'Example: {"task_type": "code", "summary": "Build a CLI todo app in Python"}\n\n'
        "No markdown, no explanation - only JSON."
    )

    logger.info(f"[analyzing_node] Calling LLM with prompt: {prompt[:100]}...")
    # Use the sync, non-streaming path: classification is an internal state, not
    # a user-visible response. Streaming would forward the model's chain-of-thought
    # ("We need to output JSON...") to the WebSocket as visible "thinking" text.
    # The JSON extraction below already handles any preamble in the response.
    full_response = await llm.generate(prompt, model_type="fast")
    logger.info(
        f"[analyzing_node] LLM response: {full_response[:200] if full_response else 'EMPTY'}"
    )

    # Extraire le JSON même si le modèle met du "Thinking Process" avant
    task_json = full_response
    json_match = re.search(r"\{[\s\S]*\}", full_response)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, dict) and "task_type" in parsed:
                task_json = json.dumps(parsed)
        except json.JSONDecodeError:
            pass

    _emit_step("analyzing", f"Tâche classifiée: {task_json[:80]}...")
    state["task_type"] = task_json
    # NOTE: do NOT append the classification to state["messages"]. The
    # streaming layer (streaming.py:188-213) iterates LangGraph events and
    # yields any new assistant message as a [TOKEN] to the WebSocket. The
    # classification is already correctly surfaced as a [STEP] event by
    # streaming.py:154-157 via state["task_type"], so an additional entry
    # in state["messages"] would leak the JSON to the user as a visible
    # "thinking" token. Downstream nodes read state["task_type"] directly.
    return state


async def planning_node(state: AgentState) -> AgentState:
    _emit_step("planning", "Creation du plan d'implementation...")

    user_model, user_provider = _get_model_info(state)
    # Per-node routing: planning needs structured JSON output with
    # multi-step reasoning — a small model (1.2B) tends to produce
    # minimal/empty plans. Force the preset's "reasoning" slot when
    # node_routing_enabled; otherwise user_model wins.
    force_model = _force_model_for("reasoning")
    routing_state = "on" if force_model else "off (user model)"
    logger.info(
        f"[planning_node] user_model={user_model} → force_model={force_model or user_model} (tier=reasoning, routing={routing_state})"
    )

    from .llm_wrapper import LLMWrapper

    llm = LLMWrapper(
        _get_llm_router(), user_model, user_provider, force_model=force_model
    )
    user_message = _get_user_message(state)

    _emit_step("planning", "Consultation du LLM pour le plan...")
    prompt = (
        f"Demande utilisateur : {user_message}\n\n"
        "Crée un plan d'implémentation détaillé. Réponds UNIQUEMENT avec cette structure JSON — "
        "pas de markdown, pas de blocs de code, pas d'explication :\n\n"
        "{\n"
        '  "steps": [\n'
        '    {"description": "description de l étape", "file": "main.py", "approach": "comment faire"}\n'
        "  ],\n"
        '  "files": {"main.py": "description du fichier"}\n'
        "}\n\n"
        'Exemple complet : {"steps": [{"description": "Créer une fonction fetch", "file": "main.py", "approach": "Utiliser requests"}], "files": {"main.py": "Point d entrée"}}\n\n'
        "Règles :\n"
        "- steps est une liste d'étapes (peut être vide)\n"
        "- files est un dictionnaire clé=valeur avec des noms de fichiers en .py\n"
        "- UNIQUEMENT du JSON valide — ni ```json, ni ```, ni texte autour\n"
        "- Commence directement par { et finis directement par }"
    )

    full_response = await llm.run_node(
        prompt, model_type="reasoning", strip_markdown=True
    )

    _emit_step("planning", "Parsing et validation du plan...")

    def _parse_plan(text: str) -> PlanData:
        """Multi-strategy JSON extraction for plan."""
        # Strategy 1: direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: extract ```json block
        json_block = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if json_block:
            try:
                return json.loads(json_block.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 3: balanced-brace scan, first valid top-level object wins.
        # Replaces a greedy regex that failed when the LLM added prose with
        # {...} placeholders (e.g. "{requests}") before/after the JSON — the
        # greedy `\{[\s\S]*\}` would span the whole response including prose,
        # producing invalid JSON and forcing the empty-plan fallback.
        depth = 0
        start = -1
        in_string = False
        escape = False
        candidates: list[str] = []
        for i, ch in enumerate(text):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start >= 0:
                        candidates.append(text[start : i + 1])
                        start = -1
        for cand in candidates:
            try:
                return json.loads(cand)
            except json.JSONDecodeError:
                continue

        # Strategy 4: repair common LLM mistakes (trailing comma, single quotes)
        import ast

        cleaned = text.strip()
        # Replace single quotes with double (except inside strings)
        cleaned = re.sub(r"(?<!\\)'", '"', cleaned)
        # Remove trailing commas before ]
        cleaned = re.sub(r",\s*]", "]", cleaned)
        # Remove trailing commas before }
        cleaned = re.sub(r",\s*}", "}", cleaned)
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback
        logger.warning("Could not parse plan from LLM response, using empty plan")
        return {"raw": text[:500], "steps": [], "files": {}}

    plan = _parse_plan(full_response)

    state["plan"] = _clean_plan(plan)
    steps_count = len(state.get("plan", {}).get("steps", []))
    files_count = len(state.get("plan", {}).get("files", {}))
    _emit_step("planning", f"Plan créé avec {steps_count} étapes")
    # Append a SHORT human-readable intro instead of the raw plan JSON.
    # The streaming layer (streaming.py) tracks the last assistant message
    # and emits its tokens to the user. Appending the full plan dict here
    # would surface the JSON to the user as visible text — the plan is
    # already shown step-by-step in the AgentSteps UI via [STEP] events,
    # so a brief intro is the right surface here. The actual executed
    # output is appended later by executing_node as a final summary.
    intro = (
        f"I'll implement this with {steps_count} step(s) across "
        f"{files_count} file(s). Generating the code now..."
    )
    state["messages"].append({"role": "assistant", "content": intro})
    return state


async def coding_node(state: AgentState) -> AgentState:
    _emit_step("coding", "Generation du code...")

    user_model, user_provider = _get_model_info(state)
    # Per-node routing: code generation is the heaviest LLM task. Small
    # models (1.2B) ignore explicit constraints (e.g. "stdlib only") and
    # hallucinate API endpoints/keys. Force the preset's "reasoning"
    # slot (9B+) when node_routing_enabled; otherwise user_model wins.
    force_model = _force_model_for("reasoning")
    routing_state = "on" if force_model else "off (user model)"
    logger.info(
        f"[coding_node] user_model={user_model} → force_model={force_model or user_model} (tier=reasoning, routing={routing_state})"
    )

    from .llm_wrapper import LLMWrapper

    llm = LLMWrapper(
        _get_llm_router(), user_model, user_provider, force_model=force_model
    )
    user_message = _get_user_message(state)
    plan_clean = _clean_plan(state.get("plan", {}))
    attempt = state.get("attempt", 0)
    previous_error = state.get("error") or (state.get("execution_result") or {}).get("error")

    prompt_parts = [f"User request: {user_message}"]

    if plan_clean:
        prompt_parts.append(f"Implementation plan: {json.dumps(plan_clean, ensure_ascii=False)}")

    # Retry path: when attempt > 0, build a structured self-correction
    # prompt that hands the model the previous code, the execution
    # error, and the review issues/suggestions. The helper returns an
    # empty string when there is nothing to fix (attempt == 0) so we
    # can append unconditionally. We lower the temperature on retries
    # (0.25 instead of 0.3) to favour deterministic, targeted fixes
    # over creative rewrites. `settings.advanced_self_critique` flips
    # between the basic prompt and the CoT+self-critique variant.
    is_fix_attempt = attempt > 0 and bool(previous_error or state.get("review"))
    if is_fix_attempt:
        fix_ctx = format_fix_prompt(
            state, advanced=bool(getattr(settings, "advanced_self_critique", False))
        )
        if fix_ctx:
            prompt_parts.append(fix_ctx)
            logger.info(
                f"[coding_node] fix attempt {attempt}/"
                f"{state.get('max_attempts', 3)} — advanced={settings.advanced_self_critique}"
            )

    prompt_parts.append(
        "Generate Python code that solves the request.\n\n"
        "FORMAT — use exactly this structure (the example is a dummy, replace with real code):\n"
        "## main.py\n"
        "```python\n"
        "print('real code here')\n"
        "```\n\n"
        "ABSOLUTE RULES:\n"
        "- Put the filename on a line starting with ##, then the ```python block right after\n"
        "- The code block MUST contain ONLY valid Python — no prose, no comments about the code\n"
        "- Do NOT explain what the code does — the code IS the answer\n"
        "- Do NOT include the planning instructions or this prompt in the output\n"
        "- Do NOT add any text outside the ## filename / ```python structure\n"
        "- Do NOT use `import requests` or `import httpx` in the example — the example is a FORMAT template, not a content suggestion\n"
        "- One file per ## header + ```python block. Multiple files = multiple ## headers, each followed by its own block\n\n"
        "CODE QUALITY (apply unless the user explicitly opts out):\n"
        "- Entry-point file MUST use `if __name__ == '__main__':` guard so it can be safely imported without side effects\n"
        "- All HTTP calls MUST have an explicit `timeout` argument (e.g. `timeout=10`). Never call `urlopen()` without a timeout\n"
        "- Wrap network, HTTP-status, and parse failures in a single `try/except` with three distinct branches:\n"
        "    except urllib.error.URLError as e:   # network / DNS / connection refused\n"
        "    except urllib.error.HTTPError as e:  # server returned 4xx / 5xx\n"
        "    except json.JSONDecodeError:         # response was not valid JSON\n"
        "  Each branch MUST print a different, human-readable message so the failure mode is obvious\n"
        "- Use `with urllib.request.urlopen(...) as resp:` for auto-cleanup of the HTTP connection\n"
        "- Do NOT invent API keys. Free public APIs (Open-Meteo, wttr.in, ipapi.co, CoinGecko, etc.) require no key. If you receive 401/403, the URL or parameter is wrong, not the key\n"
        "- When the user specifies an output format (table, list, JSON, CSV, …), follow it EXACTLY — don't downgrade to bare `print()` calls\n"
        "- Raise `ValueError` for bad inputs, `RuntimeError` for runtime failures. Do NOT `print('error:', e); sys.exit(1)` — callers and the auto-fix loop need to see the exception"
    )

    # Constraint reinforcement: if the user explicitly forbids `requests` /
    # `httpx` (e.g. "stdlib only", "no requests", "urllib only"), the model
    # is shown to ignore the rule. This block is a "negative example + good
    # example" pair to push it the right way. The sanitizer in code_sanitizer
    # provides a runtime safety net, but we still try to teach the model first.
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
    if stdlib_only_hint:
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
    # Lower temperature on retries so the model converges on a fix
    # rather than exploring variants. 0.25 is the same value proposed
    # in the fix_prompts docstring — small enough to be deterministic,
    # large enough not to be brittle.
    retry_temperature = 0.25 if is_fix_attempt else 0.3
    full_response = await llm.run_node(
        prompt, model_type="fast", temperature=retry_temperature
    )

    _emit_step("coding", "Extraction et validation du code...")
    from .code_extractor import extract_code_dict
    from .code_sanitizer import sanitize_files

    state["code"] = extract_code_dict(full_response)

    # Runtime safety net: even with the negative example in the prompt, the
    # model frequently still imports `requests` or `httpx` (we observed this
    # on 1.2B, 9B and 35B models in the live test). The sanitizer detects
    # such imports and prepends a urllib-backed compatibility shim so the
    # code runs in our sandbox without `requests` / `httpx` being installed.
    original_files = state["code"].get("files", {})
    sanitized_files, sanitize_meta = sanitize_files(original_files)
    state["code"]["files"] = sanitized_files
    state["code"]["sanitize_meta"] = sanitize_meta

    for inj in sanitize_meta.get("injections", []):
        logger.info(
            f"[coding_node] Injected stdlib shim for '{inj['package']}' in {inj['file']} "
            f"(user requested stdlib-only; model ignored)"
        )

    files_count = len(state["code"].get("files", {}))
    _emit_step("coding", f"Code généré: {files_count} fichiers")
    return state


async def reviewing_node(state: AgentState) -> AgentState:
    _emit_step("reviewing", "Analyse statique du code...")

    user_model, user_provider = _get_model_info(state)
    # Per-node routing: review needs a model that can follow the
    # "{passed, issues, suggestions}" envelope directive. Small models
    # (1.2B) frequently return a bare list of issues or hallucinate
    # problems. Force the preset's "reasoning" slot for stability
    # when node_routing_enabled; otherwise user_model wins.
    force_model = _force_model_for("reasoning")
    routing_state = "on" if force_model else "off (user model)"
    logger.info(
        f"[reviewing_node] user_model={user_model} → force_model={force_model or user_model} (tier=reasoning, routing={routing_state})"
    )

    from .llm_wrapper import LLMWrapper

    llm = LLMWrapper(
        _get_llm_router(), user_model, user_provider, force_model=force_model
    )
    code = state.get("code", {})

    # No-code short-circuit: if coding_node produced an empty files dict
    # (typical when the LLM stream returned empty content — see the
    # "stream summary" telemetry in _openai_mixin.astream), skip the
    # review. The LLM would happily "pass" an empty dict, the executor
    # would then fail with "no files to run", and the fix loop would
    # re-call coding_node with the same model + same prompt, producing
    # the same empty response and wasting ~6 minutes of retries.
    # should_continue matches on the exact "No code was generated" string
    # below to short-circuit out of the fix loop.
    files = code.get("files", {}) if isinstance(code, dict) else {}
    if not files:
        _emit_step(
            "reviewing",
            "❌ Aucun code généré par coding_node — review ignorée",
        )
        state["review"] = {
            "passed": False,
            "score": 0.0,
            "issues": [
                "No code was generated by coding_node (LLM returned an "
                "empty response). See run.log for the 'stream summary' "
                "telemetry line that explains why.",
            ],
            "suggestions": [
                "Try a different model (a larger or non-thinking model)",
                "Check LLM_TIMEOUT and max_tokens in Settings",
                "Simplify the user request if the prompt is long",
            ],
            "issue_severities": ["high"],
        }
        return state

    _emit_step("reviewing", "Vérification de la qualité du code...")
    # Multi-line template + explicit "OBJET JSON" directive + "PAS une liste"
    # warning reduce the failure mode where the model outputs the issues as
    # a bare array (e.g. ["issue 1", "issue 2"]) instead of the full
    # {passed, issues, suggestions} envelope. The parser below also handles
    # the list shape as a graceful degradation. The "score" field is a
    # 0.0-1.0 quality score that the LLM is asked to fill in — we
    # prefer it when present, fall back to a heuristic when missing.
    prompt = (
        "Tu es un relecteur de code. Analyse le code ci-dessous et réponds "
        "UNIQUEMENT avec un OBJET JSON (PAS une liste, PAS un tableau, "
        "PAS du markdown) contenant EXACTEMENT ces quatre clés :\n\n"
        "{\n"
        '  "passed": <bool>,\n'
        '  "score": <float entre 0.0 et 1.0>,\n'
        '  "issues": [<string>, ...],\n'
        '  "suggestions": [<string>, ...]\n'
        "}\n\n"
        "Règles :\n"
        "- passed=true SI le code est syntaxiquement correct ET fait ce qui est attendu\n"
        "- passed=false UNIQUEMENT s'il y a une vraie erreur (import manquant, variable indéfinie, boucle infinie)\n"
        "- Ne mets pas passed=false pour des problèmes de style ou d'optimisation\n"
        "- score: qualité globale du code (1.0 = parfait, 0.0 = inutilisable)\n"
        "        Pondère : -0.2 par erreur bloquante, -0.1 par problème de qualité, -0.05 par suggestion\n"
        "- issues : liste de chaînes (vide si passed=true)\n"
        "- suggestions : peut être vide\n\n"
        "Code à analyser :\n"
        f"{json.dumps(code, ensure_ascii=False)}\n\n"
        "Réponds UNIQUEMENT avec l'objet JSON, rien d'autre."
    )

    full_response = await llm.run_node(prompt, model_type="reasoning")
    logger.info(
        f"[reviewing_node] LLM response: {full_response[:200] if full_response else 'EMPTY'}"
    )

    # Review must be a JSON OBJECT with at least a "passed" key, but small
    # or MoE models sometimes return a JSON ARRAY instead of the envelope.
    # Two failure modes seen in the wild:
    #   - [{"passed": true, ...}]              (list of dict)
    #   - ["API_KEY manquant", "..."]]         (list of strings, often with
    #                                            trailing ]])
    # Without the multi-strategy parser below, review.get("passed") crashes
    # the whole stream with AttributeError, or silently shows a misleading
    # "Parse error" to the user.
    _REVIEW_FALLBACK: ReviewData = {
        "passed": False,
        "issues": ["Parse error"],
        "suggestions": ["Could not parse review response"],
    }

    def _coerce_to_dict(obj: object) -> ReviewData | None:
        return obj if isinstance(obj, dict) else None  # type: ignore[return-value]

    def _list_as_review(obj: list) -> ReviewData | None:
        """Recover a review dict from a list response.

        - list[str]      -> the model is listing issues; passed=False
        - list[dict]     -> take the first dict (likely the review envelope)
        - mixed          -> take the first dict, else the first string
        """
        if not obj:
            return None
        if all(isinstance(x, str) for x in obj):
            return {"passed": False, "issues": list(obj), "suggestions": []}
        for x in obj:
            if isinstance(x, dict):
                coerced = _coerce_to_dict(x)
                if coerced is not None:
                    return coerced
        return None

    def _parse_review(text: str) -> ReviewData:
        """Multi-strategy JSON extraction for review responses.

        Tries, in order:
        1. Direct json.loads — must be a dict
        2. First top-level {...} block — must be a dict
        3. First top-level [...] block — list of strings or list of dicts
        4. Fallback
        """
        # 1. Direct parse
        try:
            coerced = _coerce_to_dict(json.loads(text))
            if coerced is not None:
                return coerced
        except json.JSONDecodeError:
            pass

        # 2. First top-level {...} block
        obj_block = re.search(r"\{[\s\S]*\}", text)
        if obj_block:
            try:
                coerced = _coerce_to_dict(json.loads(obj_block.group(0)))
                if coerced is not None:
                    return coerced
            except json.JSONDecodeError:
                pass

        # 3. First top-level [...] block (handles bare list-of-issues)
        list_block = re.search(r"\[[\s\S]*?\]", text)
        if list_block:
            try:
                parsed_list = json.loads(list_block.group(0))
                if isinstance(parsed_list, list):
                    recovered = _list_as_review(parsed_list)
                    if recovered is not None:
                        return recovered
            except json.JSONDecodeError:
                pass

        return _REVIEW_FALLBACK

    review = _parse_review(full_response)

    # Post-parse enrichment. Two new fields on top of the existing
    # {passed, issues, suggestions} envelope:
    #
    #   score           : 0.0-1.0 quality score. Prefer the LLM's value
    #                     when it's a well-formed float in range;
    #                     otherwise fall back to the deterministic
    #                     heuristic. This means an old-style LLM that
    #                     omits "score" still produces a usable number.
    #   issue_severities: parallel array to `issues`, classifying each
    #                     issue as "high" / "medium" / "low" via the
    #                     keyword heuristic. This is used by
    #                     `format_fix_prompt` to prefix the most
    #                     important issues first when surfacing the
    #                     review in a retry prompt.
    issues = list(review.get("issues") or [])
    suggestions = list(review.get("suggestions") or [])
    review["issue_severities"] = [_classify_issue_severity(i) for i in issues]

    raw_score = review.get("score")
    if isinstance(raw_score, (int, float)) and 0.0 <= float(raw_score) <= 1.0:
        review["score"] = float(raw_score)
    else:
        review["score"] = _heuristic_review_score(issues, suggestions)

    state["review"] = review
    if review.get("passed"):
        _emit_step("reviewing", "✅ Review OK - code valide")
    else:
        issues_count = len(review.get("issues", []))
        _emit_step("reviewing", f"⚠️ {issues_count} problème(s) détecté(s)")
    return state


async def executing_node(state: AgentState) -> AgentState:
    _emit_step("executing", "Préparation du sandbox...")

    from backend.infrastructure.code_execution import CodeExecutionService

    executor = CodeExecutionService()
    files = state.get("code", {}).get("files", {})

    _emit_step("executing", f"Exécution de {len(files)} fichier(s) dans le sandbox...")
    try:
        try:
            result = await asyncio.wait_for(
                executor.run_files_async(files),
                timeout=float(settings.executor_timeout),
            )
        except asyncio.TimeoutError:
            # asyncio.TimeoutError has str(e) == '' — surface a useful message
            # so the user sees WHY execution failed (otherwise error field is empty).
            timeout_s = int(float(settings.executor_timeout))
            err_msg = (
                f"Execution timed out after {timeout_s}s "
                f"(sandbox exceeded EXECUTOR_TIMEOUT). "
                f"Increase executor_timeout in Settings, or simplify the code."
            )
            state["error"] = err_msg
            state["execution_result"] = {"success": False, "error": err_msg, "output": ""}
            _emit_step("executing", f"❌ Timeout ({timeout_s}s)")
            logger.warning("Sandbox execution timed out after %ss", timeout_s)
            state["attempt"] = state.get("attempt", 0) + 1
            # Skip the success-summary path and emit a failure summary instead.
            return _build_execution_summary(state)

        except asyncio.CancelledError:
            err_msg = "Execution was cancelled (e.g. client disconnect or shutdown)"
            state["error"] = err_msg
            state["execution_result"] = {"success": False, "error": err_msg, "output": ""}
            _emit_step("executing", "❌ Cancelled")
            logger.warning("Sandbox execution cancelled")
            state["attempt"] = state.get("attempt", 0) + 1
            return _build_execution_summary(state)

        # Stocker en dict (pas dataclass) pour compatibilité TypedDict
        state["execution_result"] = {
            "success": result.success,
            "error": result.error,
            "output": result.output,
        }
        state["error"] = None
        if result.success:
            _emit_step("executing", "✅ Exécution réussie")
        else:
            # Defense in depth: if the upstream executor returned success=False
            # with an empty error, generate a meaningful fallback so the user
            # never sees a silent empty failure.
            err_msg = result.error or "(no error message from sandbox — check executor logs)"
            _emit_step("executing", f"❌ Échec: {err_msg[:80]}")
    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}" if str(e) else f"{type(e).__name__} (no message)"
        state["error"] = err_msg
        state["execution_result"] = {"success": False, "error": err_msg, "output": ""}
        _emit_step("executing", f"❌ Exception: {err_msg[:80]}")
        logger.exception("Execution failed")

    state["attempt"] = state.get("attempt", 0) + 1

    return _build_execution_summary(state)


def _build_execution_summary(state: AgentState) -> AgentState:
    """Append a final user-facing summary to state["messages"].

    The streaming layer (streaming.py) tracks the LAST assistant message
    in state["messages"] and emits its tokens — appending here puts the
    executed output (or the failure trace) in front of the user.

    On a successful run, this includes the sandbox stdout. On failure,
    it shows the error so the user can see what went wrong.

    Returns the state for fluent chaining from error/timeout paths.
    """
    exec_result = state.get("execution_result") or {}
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    files_written = exec_result.get("files_written") or list(
        (state.get("code") or {}).get("files", {}).keys()
    )

    if exec_result.get("success"):
        output = (exec_result.get("output") or "").strip()
        parts = ["✅ Code executed successfully."]
        if output:
            truncated = output[:2000]
            if len(output) > 2000:
                truncated += "\n... (truncated, full output in execution_result)"
            parts.append(f"\n\n**Output:**\n```\n{truncated}\n```")
        if files_written:
            parts.append(
                f"\n\n**Generated file(s):** `{', '.join(files_written)}`"
            )
        parts.append(f"\n\n_Attempt {attempt}/{max_attempts}._")
        summary = "\n".join(parts)
    else:
        error_text = (exec_result.get("error") or "").strip()
        if not error_text:
            error_text = "(no error message captured by the sandbox)"
        summary = (
            f"❌ Execution failed (attempt {attempt}/{max_attempts})\n\n"
            f"**Error:**\n```\n{error_text[:1000]}\n```"
        )

    state["messages"].append({"role": "assistant", "content": summary})
    return state


def should_continue(state: AgentState) -> Literal["fix_code", "end"]:
    review = state.get("review")
    execution_result = state.get("execution_result")
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)

    # Priorité 0: reviewing_node a détecté un code vide (LLM stream
    # retourné vide). Ce check doit être AVANT les Priorités 1-3 qui
    # traitent execution_result, car l'exécuteur tourne après le
    # reviewing_node et produit un échec "no files to run" — le sentinel
    # doit être capturé indépendamment de ce que l'exécuteur a fait.
    if review is not None:
        issues = review.get("issues") or []
        if any("No code was generated" in str(i) for i in issues):
            _emit_step(
                "no_code_short_circuit",
                "❌ coding_node returned no code; skipping auto-fix loop",
            )
            return "end"

    # Priorité 1: exécution réussie → STOP (le code marche, inutile de boucler)
    if execution_result is not None:
        result_dict: dict = execution_result  # type: ignore[assignment]
        if result_dict.get("success", False):
            _emit_step("execution_success", "[OK] Execution succeeded")
            return "end"

    # Priorité 2: échec d'exécution + tentatives épuisées → STOP
    if execution_result is not None:
        result_dict: dict = execution_result  # type: ignore[assignment]
        if not result_dict.get("success", False) and attempt >= max_attempts:
            error_msg = result_dict.get("error", "unknown error")
            _emit_step("execution_failed", f"❌ Execution failed (max {max_attempts} tentatives): {error_msg[:80]}")
            return "end"

    # Priorité 3: échec d'exécution + tentatives restantes → auto-fix
    if execution_result is not None:
        result_dict: dict = execution_result  # type: ignore[assignment]
        if not result_dict.get("success", False):
            error_msg = result_dict.get("error", "unknown error")
            _emit_step("fixing", f"Auto-fix execution ({attempt + 1}/{max_attempts}): {error_msg[:60]}")
            return "fix_code"

    # Priorité 4: max attempts atteint → STOP
    if attempt >= max_attempts:
        _emit_step("max_attempts_reached", f"Max attempts ({max_attempts}) reached")
        return "end"

    # Priorité 5: reviewing_node a détecté un code vide (LLM stream
    # retourné vide). L'exécuteur a déjà échoué (pas de fichiers à
    # exécuter) ou ne s'est jamais lancé. Boucler vers coding_node
    # avec le même modèle + même prompt ne ferait que reproduire la
    # réponse vide — on coupe court pour épargner les ~6 minutes de
    # fix attempts inutiles. L'utilisateur voit un message clair dans
    # l'UI et peut retry manuellement avec un autre modèle.
    if review is not None:
        issues = review.get("issues") or []
        if any("No code was generated" in str(i) for i in issues):
            _emit_step(
                "no_code_short_circuit",
                "❌ coding_node returned no code; skipping auto-fix loop",
            )
            return "end"

    # Sinon: auto-fix → retour au coding
    _emit_step("fixing", f"Auto-fix attempt {attempt + 1}/{max_attempts}")
    return "fix_code"
