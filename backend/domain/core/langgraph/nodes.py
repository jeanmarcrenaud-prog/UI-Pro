"""LangGraph pipeline nodes."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Literal

from models.settings import settings

logger = logging.getLogger(__name__)


# ========================================
# Helpers
# ========================================

def _get_user_message(state: dict[str, Any]) -> str:
    messages = state.get("messages", [])
    return messages[0].get("content", "") if messages else ""


def _get_model_info(state: dict[str, Any]) -> tuple[str, str]:
    metadata = state.get("metadata", {})
    return metadata.get("model", ""), metadata.get("provider", "ollama")


def _clean_plan(plan: dict[str, Any]) -> dict[str, Any]:
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
        try:
            message.encode("cp1252").decode("cp1252")
        except (UnicodeEncodeError, UnicodeDecodeError):
            message = message.encode("ascii", "replace").decode("ascii")
        from backend.domain.core.events import emit_agent_step
        emit_agent_step(phase, message)
    except Exception:
        pass


# ========================================
# Nodes
# ========================================

async def analyzing_node(state):
    _emit_step("analyzing", "Analyse des exigences...")

    user_model, user_provider = _get_model_info(state)
    logger.info(f"[analyzing_node] model={user_model}, provider={user_provider}")

    from .llm_wrapper import LLMWrapper
    llm = LLMWrapper(_get_llm_router(), user_model, user_provider)
    user_message = _get_user_message(state)

    prompt = (
        f"User request: {user_message}\n\n"
        "Classify the task type and respond with ONLY valid JSON:\n"
        '{"task_type": "code|reasoning|general", "summary": "brief description"}\n'
        "No markdown, no explanation - only JSON."
    )

    logger.info(f"[analyzing_node] Calling LLM with prompt: {prompt[:100]}...")
    full_response = await llm.run_node(prompt, model_type="reasoning")
    logger.info(f"[analyzing_node] LLM response: {full_response[:200] if full_response else 'EMPTY'}")

    state["messages"].append({"role": "assistant", "content": full_response})
    return state


async def planning_node(state):
    _emit_step("planning", "Creation du plan d'implementation...")

    user_model, user_provider = _get_model_info(state)
    from .llm_wrapper import LLMWrapper
    llm = LLMWrapper(_get_llm_router(), user_model, user_provider)
    user_message = _get_user_message(state)

    prompt = (
        f"User request: {user_message}\n\n"
        "Create a detailed implementation plan as VALID JSON ONLY. "
        "No markdown, no code blocks, no explanations - ONLY raw JSON.\n"
        '{"steps": [{"description": "...", "file": "...", "approach": "..."}], "files": {"filename.py": "brief description"}}\n'
        "Respond with ONLY the JSON object."
    )

    full_response = await llm.run_node(prompt, model_type="reasoning", strip_markdown=True)

    try:
        plan = json.loads(full_response)
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
    state["messages"].append({"role": "assistant", "content": str(state["plan"])})
    return state


async def coding_node(state):
    _emit_step("coding", "Generation du code...")

    user_model, user_provider = _get_model_info(state)
    from .llm_wrapper import LLMWrapper
    llm = LLMWrapper(_get_llm_router(), user_model, user_provider)
    user_message = _get_user_message(state)
    plan_clean = _clean_plan(state.get("plan", {}))

    prompt = (
        f"User request: {user_message}\n\n"
        f"Implementation plan: {json.dumps(plan_clean, ensure_ascii=False)}\n\n"
        "IMPORTANT: Return ONLY valid JSON. No markdown, no explanations.\n"
        '{"files": {"filename.py": "python code - NO comments, NO docstrings, ONLY executable code"}}\n'
        "Write complete, working Python code. No prose, no comments, no markdown."
    )

    full_response = await llm.run_node(prompt, model_type="fast", temperature=0.3)
    from .code_extractor import extract_code_dict
    state["code"] = extract_code_dict(full_response)
    return state


async def reviewing_node(state):
    _emit_step("reviewing", "Code Review & Security Check...")

    user_model, user_provider = _get_model_info(state)
    from .llm_wrapper import LLMWrapper
    llm = LLMWrapper(_get_llm_router(), user_model, user_provider)
    code = state.get("code", {})

    prompt = f"Analyse ce code de façon critique et retourne un JSON:\n{json.dumps(code, ensure_ascii=False)}"

    full_response = await llm.run_node(prompt, model_type="reasoning")

    try:
        review = json.loads(full_response)
    except Exception:
        review = {"passed": False, "issues": [], "suggestions": ["Could not parse review"]}

    state["review"] = review
    return state


async def executing_node(state):
    _emit_step("executing", "Execution dans le sandbox...")

    from backend.infrastructure.code_execution import CodeExecutionService
    executor = CodeExecutionService()
    files = state.get("code", {}).get("files", {})

    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: executor.run(files)),
            timeout=float(settings.executor_timeout),
        )
        state["execution_result"] = result
        state["error"] = None
    except Exception as e:
        state["error"] = str(e)
        state["execution_result"] = {"success": False, "error": str(e)}
        logger.exception("Execution failed")

    state["attempt"] = state.get("attempt", 0) + 1
    return state


def should_continue(state) -> Literal["review", "end"]:
    review = state.get("review")
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)

    if review and review.get("passed", False):
        _emit_step("review_passed", "[OK] Code review passed")
        return "end"

    if attempt >= max_attempts:
        _emit_step("max_attempts_reached", f"Max attempts ({max_attempts}) reached")
        return "end"

    _emit_step("fixing", f"Auto-fix attempt {attempt + 1}/{max_attempts}")
    return "review"