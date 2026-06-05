"""LangGraph pipeline nodes."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Literal

from models.settings import settings

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


# ========================================
# Nodes
# ========================================


def _force_model_for(tier: str) -> str:
    """Resolve the preset tier to a model name, honoring the routing toggle.

    Returns the preset's model for the given tier when per-node routing
    is enabled (the default). Returns "" (empty) when the user has
    disabled routing — the LLMWrapper then falls back to user_model,
    restoring the legacy "all nodes use the chat model" behavior.
    """
    if not settings.get_node_routing_enabled():
        return ""
    return settings.get_model_for_task(tier)


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

        # Strategy 3: first top-level {…} object
        brace_match = re.search(r"\{[\s\S]*\}", text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

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

    if attempt > 0 and previous_error:
        prompt_parts.append(
            f"PREVIOUS EXECUTION FAILED (attempt {attempt}/{state.get('max_attempts', 3)}):\n"
            f"Error: {previous_error[:500]}\n\n"
            "Fix the code to resolve this error. Do NOT repeat the same mistake."
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
    full_response = await llm.run_node(prompt, model_type="fast", temperature=0.3)

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

    _emit_step("reviewing", "Vérification de la qualité du code...")
    # Multi-line template + explicit "OBJET JSON" directive + "PAS une liste"
    # warning reduce the failure mode where the model outputs the issues as
    # a bare array (e.g. ["issue 1", "issue 2"]) instead of the full
    # {passed, issues, suggestions} envelope. The parser below also handles
    # the list shape as a graceful degradation.
    prompt = (
        "Tu es un relecteur de code. Analyse le code ci-dessous et réponds "
        "UNIQUEMENT avec un OBJET JSON (PAS une liste, PAS un tableau, "
        "PAS du markdown) contenant EXACTEMENT ces trois clés :\n\n"
        "{\n"
        '  "passed": <bool>,\n'
        '  "issues": [<string>, ...],\n'
        '  "suggestions": [<string>, ...]\n'
        "}\n\n"
        "Règles :\n"
        "- passed=true SI le code est syntaxiquement correct ET fait ce qui est attendu\n"
        "- passed=false UNIQUEMENT s'il y a une vraie erreur (import manquant, variable indéfinie, boucle infinie)\n"
        "- Ne mets pas passed=false pour des problèmes de style ou d'optimisation\n"
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

    # Sinon: auto-fix → retour au coding
    _emit_step("fixing", f"Auto-fix attempt {attempt + 1}/{max_attempts}")
    return "fix_code"
