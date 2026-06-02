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


async def analyzing_node(state: AgentState) -> AgentState:
    _emit_step("analyzing", "Analyse des exigences...")

    user_model, user_provider = _get_model_info(state)
    logger.info(f"[analyzing_node] model={user_model}, provider={user_provider}")

    from .llm_wrapper import LLMWrapper

    llm = LLMWrapper(_get_llm_router(), user_model, user_provider)
    user_message = _get_user_message(state)

    _emit_step("analyzing", "Classification de la tâche...")
    prompt = (
        f"User request: {user_message}\n\n"
        "Classify the task type and respond with ONLY valid JSON:\n"
        '{"task_type": "code|reasoning|general", "summary": "brief description"}\n'
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
    state["messages"].append({"role": "assistant", "content": task_json})
    return state


async def planning_node(state: AgentState) -> AgentState:
    _emit_step("planning", "Creation du plan d'implementation...")

    user_model, user_provider = _get_model_info(state)
    from .llm_wrapper import LLMWrapper

    llm = LLMWrapper(_get_llm_router(), user_model, user_provider)
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
    _emit_step("planning", f"Plan créé avec {steps_count} étapes")
    state["messages"].append({"role": "assistant", "content": str(state["plan"])})
    return state


async def coding_node(state: AgentState) -> AgentState:
    _emit_step("coding", "Generation du code...")

    user_model, user_provider = _get_model_info(state)
    from .llm_wrapper import LLMWrapper

    llm = LLMWrapper(_get_llm_router(), user_model, user_provider)
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
        "import requests\n"
        "print('real code here')\n"
        "```\n\n"
        "ABSOLUTE RULES:\n"
        "- Put the filename on a line starting with ##, then the ```python block right after\n"
        "- The code block MUST contain ONLY valid Python — no prose, no comments about the code\n"
        "- Do NOT explain what the code does — the code IS the answer\n"
        "- Do NOT include the planning instructions or this prompt in the output\n"
        "- Do NOT add any text outside the ## filename / ```python structure"
    )

    prompt = "\n\n".join(prompt_parts)
    full_response = await llm.run_node(prompt, model_type="fast", temperature=0.3)

    _emit_step("coding", "Extraction et validation du code...")
    from .code_extractor import extract_code_dict

    state["code"] = extract_code_dict(full_response)
    files_count = len(state["code"].get("files", {}))
    _emit_step("coding", f"Code généré: {files_count} fichiers")
    return state


async def reviewing_node(state: AgentState) -> AgentState:
    _emit_step("reviewing", "Analyse statique du code...")

    user_model, user_provider = _get_model_info(state)
    from .llm_wrapper import LLMWrapper

    llm = LLMWrapper(_get_llm_router(), user_model, user_provider)
    code = state.get("code", {})

    _emit_step("reviewing", "Vérification de la qualité du code...")
    prompt = (
        "Tu es un relecteur de code. Analyse le code ci-dessous et retourne UNIQUEMENT ce JSON — "
        "pas de markdown, pas d'explication :\n\n"
        '{"passed": true, "issues": [], "suggestions": []}\n\n'
        "Code à analyser :\n"
        f"{json.dumps(code, ensure_ascii=False)}\n\n"
        "Règles :\n"
        "- passed=true SI le code est syntaxiquement correct ET fait ce qui est attendu\n"
        "- passed=false UNIQUEMENT s'il y a une vraie erreur (import manquant, variable indéfinie, boucle infinie)\n"
        "- Ne mets pas passed=false pour des problèmes de style ou d'optimisation\n"
        "- Issues : liste vide si passed=true, sinon décris l'erreur concrète\n"
        "- Suggestions : peut être vide\n"
        "- Ne commence pas par ```json — réponds DIRECTEMENT par le JSON brut"
    )

    full_response = await llm.run_node(prompt, model_type="reasoning")

    try:
        review: ReviewData = json.loads(full_response)
    except json.JSONDecodeError:
        # Fallback: extraire bloc JSON
        json_block = re.search(r"\{[\s\S]*\}", full_response)
        if json_block:
            try:
                review = json.loads(json_block.group(0))
            except Exception:
                review = {"passed": False, "issues": ["Parse error"], "suggestions": ["Could not parse review response"]}
        else:
            review = {"passed": False, "issues": ["Parse error"], "suggestions": ["Could not parse review response"]}
    except Exception:
        review = {"passed": False, "issues": ["Parse error"], "suggestions": ["Could not parse review response"]}

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
        result = await asyncio.wait_for(
            executor.run_files_async(files),
            timeout=float(settings.executor_timeout),
        )
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
            _emit_step("executing", f"❌ Échec: {result.error[:80] if result.error else 'unknown'}")
    except Exception as e:
        state["error"] = str(e)
        state["execution_result"] = {"success": False, "error": str(e)}
        _emit_step("executing", f"❌ Exception: {str(e)[:80]}")
        logger.exception("Execution failed")

    state["attempt"] = state.get("attempt", 0) + 1
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
