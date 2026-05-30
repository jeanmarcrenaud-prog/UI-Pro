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
    full_response = await llm.run_node(prompt, model_type="reasoning")
    logger.info(
        f"[analyzing_node] LLM response: {full_response[:200] if full_response else 'EMPTY'}"
    )

    _emit_step("analyzing", f"Tâche classifiée: {full_response[:80]}...")
    state["task_type"] = full_response
    state["messages"].append({"role": "assistant", "content": full_response})
    return state


async def planning_node(state: AgentState) -> AgentState:
    _emit_step("planning", "Creation du plan d'implementation...")

    user_model, user_provider = _get_model_info(state)
    from .llm_wrapper import LLMWrapper

    llm = LLMWrapper(_get_llm_router(), user_model, user_provider)
    user_message = _get_user_message(state)

    _emit_step("planning", "Consultation du LLM pour le plan...")
    prompt = (
        f"User request: {user_message}\n\n"
        "Create a detailed implementation plan as VALID JSON ONLY. "
        "No markdown, no code blocks, no explanations - ONLY raw JSON.\n"
        '{"steps": [{"description": "...", "file": "...", "approach": "..."}], "files": {"filename.py": "brief description"}}\n'
        "Respond with ONLY the JSON object."
    )

    full_response = await llm.run_node(
        prompt, model_type="reasoning", strip_markdown=True
    )

    _emit_step("planning", "Parsing et validation du plan...")
    try:
        plan: PlanData = json.loads(full_response)
    except json.JSONDecodeError:
        json_match = re.search(r"\{[\s\S]*\}", full_response)
        if json_match:
            try:
                plan = json.loads(json_match.group(0))
            except Exception:
                plan = {"raw": full_response, "steps": [], "files": {}}
        else:
            plan = {"raw": full_response, "steps": [], "files": {}}

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

    _emit_step("coding", "Génération du code par LLM...")
    prompt = (
        f"User request: {user_message}\n\n"
        f"Implementation plan: {json.dumps(plan_clean, ensure_ascii=False)}\n\n"
        "Write complete, working Python code.\n\n"
        "Output EACH file as a fenced code block with its filename on the line above:\n\n"
        "## main.py\n"
        "```python\n"
        "# python code here\n"
        "```\n\n"
        "## utils.py\n"
        "```python\n"
        "# python code here\n"
        "```\n\n"
        "Rules:\n"
        "- Every filename MUST end with .py\n"
        "- Write real, complete, executable code with all imports\n"
        "- No prose, no explanations, no thinking — only the code blocks\n"
        "- If only one file, still use the ## filename.py / ```python format"
    )

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
    prompt = f"Analyse ce code de façon critique et retourne un JSON:\n{json.dumps(code, ensure_ascii=False)}"

    full_response = await llm.run_node(prompt, model_type="reasoning")

    try:
        review: ReviewData = json.loads(full_response)
    except Exception:
        review: ReviewData = {
            "passed": False,
            "issues": [],
            "suggestions": ["Could not parse review"],
        }

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

    # Priorité 1: échec d'exécution + tentatives épuisées → STOP
    if execution_result is not None:
        result_dict: dict = execution_result  # type: ignore[assignment]
        if not result_dict.get("success", False) and attempt >= max_attempts:
            error_msg = result_dict.get("error", "unknown error")
            _emit_step("execution_failed", f"❌ Execution failed (max {max_attempts} tentatives): {error_msg[:80]}")
            return "end"

    # Priorité 2: échec d'exécution + tentatives restantes → auto-fix
    if execution_result is not None:
        result_dict: dict = execution_result  # type: ignore[assignment]
        if not result_dict.get("success", False):
            error_msg = result_dict.get("error", "unknown error")
            _emit_step("fixing", f"Auto-fix execution ({attempt + 1}/{max_attempts}): {error_msg[:60]}")
            return "fix_code"

    # Priorité 3: review passée + execution OK → STOP (succès)
    if review and review.get("passed", False):
        _emit_step("review_passed", "[OK] Code review passed")
        return "end"

    # Priorité 4: max attempts atteint → STOP
    if attempt >= max_attempts:
        _emit_step("max_attempts_reached", f"Max attempts ({max_attempts}) reached")
        return "end"

    # Sinon: auto-fix → retour au coding
    _emit_step("fixing", f"Auto-fix attempt {attempt + 1}/{max_attempts}")
    return "fix_code"
