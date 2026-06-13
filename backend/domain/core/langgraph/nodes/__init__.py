"""LangGraph pipeline nodes.

Refactored from a monolithic 1100-line module into a package:

    _base.py       Helpers, ``@_timed_node``, LLM setup, token tracking
    _coding.py     ``coding_node`` (the heaviest node)
    __init__.py    Remaining 4 nodes + ``should_continue`` + re-exports

All public symbols (node functions, ``_clean_plan``, etc.) are re-exported
here so existing callers can still ``from .nodes import analyzing_node``.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
from typing import Any, Literal

from backend.domain.settings import settings

from ..state import AgentState, PlanData, ReviewData

from ._base import (
    _build_llm,
    _classify_issue_severity,
    _clean_plan,
    _emit_step,
    _get_user_message,
    _heuristic_review_score,
    _llm_generate,
    _llm_run_node,
    _record_error,
    _step_done,
    _step_start,
    _timed_node,
)
from ._coding import coding_node

logger = logging.getLogger(__name__)

# Re-export for callers that import ``coding_node`` directly
# (``langgraph.__init__.build_graph``, tests, etc.)

__all__ = [
    "analyzing_node",
    "coding_node",
    "executing_node",
    "planning_node",
    "reviewing_node",
    "should_continue",
]


# ========================================================================
# analyzing_node
# ========================================================================


@_timed_node("analyzing")
async def analyzing_node(state: AgentState) -> dict[str, Any]:
    _step_start(state, "analyzing")
    _emit_step("analyzing", "Analyse des exigences...")

    # Per-node routing: classification is a simple task that benefits from
    # a fast, lightweight model.
    llm = _build_llm(state, "fast")

    user_message = _get_user_message(state)

    _emit_step("analyzing", "Classification de la tâche...")
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

    logger.info("[analyzing_node] Calling LLM with prompt: %s...", prompt[:100])
    full_response = await _llm_generate(llm, prompt, "analyzing", model_type="fast")
    logger.info(
        "[analyzing_node] LLM response: %s",
        full_response[:200] if full_response else "EMPTY",
    )

    # Extract JSON even if the model prepends "Thinking Process"
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
    return _step_done(state, "analyzing") | {
        "task_type": task_json,
    }


# ========================================================================
# planning_node
# ========================================================================


@_timed_node("planning")
async def planning_node(state: AgentState) -> dict[str, Any]:
    _step_start(state, "planning")
    _emit_step("planning", "Creation du plan d'implementation...")

    # Per-node routing: planning needs structured JSON output with
    # multi-step reasoning — use the "reasoning" tier.
    llm = _build_llm(state, "reasoning")

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

    full_response = await _llm_run_node(
        llm, prompt, "planning", model_type="reasoning", strip_markdown=True,
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

        # Strategy 3: balanced-brace scan
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

        # Strategy 4: repair common LLM mistakes
        import ast

        cleaned = text.strip()
        cleaned = re.sub(r"(?<!\\)'", '"', cleaned)
        cleaned = re.sub(r",\s*]", "]", cleaned)
        cleaned = re.sub(r",\s*}", "}", cleaned)
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback
        logger.warning("Could not parse plan from LLM response, using empty plan")
        _record_error(state, "planning", "Could not parse plan from LLM response")
        return {"raw": text[:500], "steps": [], "files": {}}

    plan = _parse_plan(full_response)

    state["plan"] = _clean_plan(plan)
    steps_count = len(state.get("plan", {}).get("steps", []))
    files_count = len(state.get("plan", {}).get("files", {}))
    _emit_step("planning", f"Plan créé avec {steps_count} étapes")
    intro = (
        f"I'll implement this with {steps_count} step(s) across "
        f"{files_count} file(s). Generating the code now..."
    )
    return _step_done(state, "planning") | {
        "messages": [{"role": "assistant", "content": intro}],
        "plan": state.get("plan"),
    }


# ========================================================================
# reviewing_node
# ========================================================================


@_timed_node("reviewing")
async def reviewing_node(state: AgentState) -> dict[str, Any]:
    _step_start(state, "reviewing")
    _emit_step("reviewing", "Analyse statique du code...")

    # Per-node routing: review needs a model that can follow the
    # "{passed, issues, suggestions}" envelope directive.
    llm = _build_llm(state, "reasoning")

    code = state.get("code", {})

    # No-code short-circuit
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
        return _step_done(state, "reviewing") | {
            "review": state.get("review"),
        }

    # ── Generic validation for ALL files ──
    _PYTHON_EXTS = (".py", ".pyw")
    _MAX_FILE_SIZE = 500_000
    _syntax_errors: list[str] = []
    for fname, source in files.items():
        if not isinstance(source, str):
            _syntax_errors.append(f"{fname}: contenu non-texte (type={type(source).__name__})")
            continue
        if not source.strip():
            _syntax_errors.append(f"{fname}: fichier vide")
            continue
        if len(source) > _MAX_FILE_SIZE:
            _syntax_errors.append(
                f"{fname}: fichier trop volumineux ({len(source)} > {_MAX_FILE_SIZE} octets)"
            )
            continue
        if "\0" in source:
            _syntax_errors.append(f"{fname}: contenu binaire détecté (null byte)")
            continue

        # Python-specific: ast.parse validation
        if not fname.endswith(_PYTHON_EXTS):
            continue
        try:
            ast.parse(source, filename=fname)
        except SyntaxError as exc:
            msg = f"SyntaxError dans {fname}: {exc.msg}"
            if exc.lineno:
                msg += f" (ligne {exc.lineno}"
                if exc.offset:
                    msg += f", colonne {exc.offset}"
                msg += ")"
            _syntax_errors.append(msg)

    if _syntax_errors:
        logger.warning(
            "[reviewing_node] Validation errors detected — skipping LLM review: %s",
            "; ".join(_syntax_errors),
        )
        _emit_step("reviewing", f"❌ {len(_syntax_errors)} erreur(s) de validation détectée(s)")
        state["review"] = {
            "passed": False,
            "score": 0.0,
            "issues": _syntax_errors,
            "suggestions": [
                "Fix the error(s) above and re-run",
                "Check for missing content, binary data, or syntax errors",
            ],
            "issue_severities": ["high"] * len(_syntax_errors),
        }
        _record_error(state, "reviewing", "; ".join(_syntax_errors))
        return _step_done(state, "reviewing", status="error") | {
            "review": state.get("review"),
        }

    _emit_step("reviewing", "Vérification de la qualité du code...")
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

    full_response = await _llm_run_node(llm, prompt, "reviewing", model_type="reasoning")
    logger.info(
        "[reviewing_node] LLM response: %s",
        full_response[:200] if full_response else "EMPTY",
    )

    _REVIEW_FALLBACK: ReviewData = {
        "passed": False,
        "issues": ["Parse error"],
        "suggestions": ["Could not parse review response"],
    }

    def _coerce_to_dict(obj: object) -> ReviewData | None:
        return obj if isinstance(obj, dict) else None  # type: ignore[return-value]

    def _list_as_review(obj: list) -> ReviewData | None:
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

        # 3. First top-level [...] block
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

        _record_error(state, "reviewing", "Could not parse LLM review response")
        return _REVIEW_FALLBACK

    review = _parse_review(full_response)

    # Post-parse enrichment
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
    return _step_done(state, "reviewing") | {
        "review": state.get("review"),
    }


# ========================================================================
# executing_node
# ========================================================================


@_timed_node("executing")
async def executing_node(state: AgentState) -> dict[str, Any]:
    _step_start(state, "executing")
    _emit_step("executing", "Préparation du sandbox...")

    from backend.infrastructure.code_execution import CodeExecutionService

    executor = CodeExecutionService()
    files = state.get("code", {}).get("files", {})

    from backend.domain.core.events import emit_exec_output

    session_stream = (state.get("session_id") or state.get("stream_id") or "")

    def _on_exec_line(line: str, channel: str) -> None:
        try:
            emit_exec_output(line, channel=channel, stream_id=session_stream)
        except Exception:
            pass

    _emit_step("executing", f"Exécution de {len(files)} fichier(s) dans le sandbox...")
    try:
        try:
            result = await asyncio.wait_for(
                executor.run_files_async(files, output_callback=_on_exec_line),
                timeout=float(settings.executor_timeout),
            )
        except asyncio.TimeoutError:
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
            _record_error(state, "executing", err_msg)
            state["attempt"] = state.get("attempt", 0) + 1
            return _step_done(state, "executing", status="error") | _build_execution_summary(state)

        except asyncio.CancelledError:
            err_msg = "Execution was cancelled (e.g. client disconnect or shutdown)"
            state["error"] = err_msg
            state["execution_result"] = {"success": False, "error": err_msg, "output": ""}
            _emit_step("executing", "❌ Cancelled")
            logger.warning("Sandbox execution cancelled")
            _record_error(state, "executing", err_msg)
            state["attempt"] = state.get("attempt", 0) + 1
            return _step_done(state, "executing", status="error") | _build_execution_summary(state)

        state["execution_result"] = {
            "success": result.success,
            "error": result.error,
            "output": result.output,
        }
        state["error"] = None
        if result.success:
            _emit_step("executing", "✅ Exécution réussie")
        else:
            err_msg = result.error or "(no error message from sandbox — check executor logs)"
            _emit_step("executing", f"❌ Échec: {err_msg[:80]}")
            _record_error(state, "executing", err_msg)
    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}" if str(e) else f"{type(e).__name__} (no message)"
        state["error"] = err_msg
        state["execution_result"] = {"success": False, "error": err_msg, "output": ""}
        _emit_step("executing", f"❌ Exception: {err_msg[:80]}")
        _record_error(state, "executing", err_msg)
        _step_done(state, "executing", status="error")
        logger.exception("Execution failed")

    state["attempt"] = state.get("attempt", 0) + 1
    return _step_done(state, "executing") | _build_execution_summary(state)


def _build_execution_summary(state: AgentState) -> dict[str, Any]:
    """Build a user-facing summary dict for merging into the node result.

    The returned dict should be merged via ``|`` with the step-track dict:
    ``return _step_done(...) | _build_execution_summary(state)``
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

    return {
        "messages": [{"role": "assistant", "content": summary}],
        "execution_result": state.get("execution_result"),
        "error": state.get("error"),
        "attempt": state.get("attempt"),
    }


# ========================================================================
# should_continue (conditional edge)
# ========================================================================


def should_continue(state: AgentState) -> Literal["fix_code", "end"]:
    review = state.get("review")
    execution_result = state.get("execution_result")
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)

    # Priority 0: reviewing_node detected empty code
    if review is not None:
        issues = review.get("issues") or []
        if any("No code was generated" in str(i) for i in issues):
            _emit_step(
                "no_code_short_circuit",
                "❌ coding_node returned no code; skipping auto-fix loop",
            )
            return "end"

    # Priority 1: execution succeeded → stop
    if execution_result is not None:
        result_dict: dict = execution_result  # type: ignore[assignment]
        if result_dict.get("success", False):
            _emit_step("execution_success", "[OK] Execution succeeded")
            return "end"

    # Priority 2: failed + exhausted → stop
    if execution_result is not None:
        result_dict: dict = execution_result  # type: ignore[assignment]
        if not result_dict.get("success", False) and attempt >= max_attempts:
            error_msg = result_dict.get("error", "unknown error")
            _emit_step(
                "execution_failed",
                f"❌ Execution failed (max {max_attempts} tentatives): {error_msg[:80]}",
            )
            return "end"

    # Priority 3: failed + retries left → fix_code
    if execution_result is not None:
        result_dict: dict = execution_result  # type: ignore[assignment]
        if not result_dict.get("success", False):
            error_msg = result_dict.get("error", "unknown error")
            _emit_step(
                "fixing",
                f"Auto-fix execution ({attempt + 1}/{max_attempts}): {error_msg[:60]}",
            )
            return "fix_code"

    # Priority 4: max attempts reached → stop
    if attempt >= max_attempts:
        _emit_step("max_attempts_reached", f"Max attempts ({max_attempts}) reached")
        return "end"

    # Priority 5: reviewing_node detected empty code (re-check)
    if review is not None:
        issues = review.get("issues") or []
        if any("No code was generated" in str(i) for i in issues):
            _emit_step(
                "no_code_short_circuit",
                "❌ coding_node returned no code; skipping auto-fix loop",
            )
            return "end"

    # Default: auto-fix
    _emit_step("fixing", f"Auto-fix attempt {attempt + 1}/{max_attempts}")
    return "fix_code"
