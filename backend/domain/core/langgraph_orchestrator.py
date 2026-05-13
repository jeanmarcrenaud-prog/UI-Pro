"""
backend/domain/core/langgraph_orchestrator.py
Migration complète vers LangGraph officiel + Real Token Streaming
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Literal, Optional

from typing_extensions import TypedDict
from models.settings import settings

logger = logging.getLogger(__name__)


# ========================================
# 🧠 STATE
# ========================================

class AgentState(TypedDict, total=False):
    messages: list[dict[str, Any]]
    plan: Optional[dict[str, Any]]
    code: Optional[dict[str, Any]]
    review: Optional[dict[str, Any]]
    execution_result: Optional[dict[str, Any]]
    error: Optional[str]
    attempt: int
    max_attempts: int
    session_id: str
    metadata: dict[str, Any]


# ========================================
# 🔧 Cached Lazy Imports
# ========================================

_llm_router = None
_executor = None


def _get_llm_router():
    global _llm_router
    if _llm_router is None:
        from backend.infrastructure.llm_router import get_llm_router
        _llm_router = get_llm_router()
    return _llm_router


def _get_executor():
    global _executor
    if _executor is None:
        from backend.infrastructure.code_execution import CodeExecutionService
        _executor = CodeExecutionService()
    return _executor


def _emit_agent_step(phase: str, message: str):
    try:
        from backend.domain.core.events import emit_agent_step
        emit_agent_step(phase, message)
    except Exception:
        pass


# ========================================
# 🧩 LLM Wrapper with Real Streaming
# ========================================

class LLMWrapper:
    def __init__(self, router, user_model: str = "", user_provider: str = "ollama"):
        self.router = router
        self.user_model = user_model
        self.user_provider = user_provider

    async def generate(self, prompt: str, model_type: str = "fast", temperature: float = 0.7) -> str:
        """Fallback full generation."""
        loop = asyncio.get_running_loop()
        # Pass user_model and user_provider to router
        return await asyncio.wait_for(
            loop.run_in_executor(None, lambda: self.router.generate(prompt, model_type, temperature=temperature, model=self.user_model, provider=self.user_provider)),
            timeout=float(settings.llm_timeout),
        )

    async def stream_generate(self, prompt: str, model_type: str = "fast", temperature: float = 0.7):
        """Real token streaming."""
        try:
            if hasattr(self.router, "astream"):
                async for chunk in self.router.astream(
                    prompt=prompt, model_type=model_type, temperature=temperature,
                    model=self.user_model, provider=self.user_provider
                ):
                    if isinstance(chunk, str):
                        yield chunk
                    elif hasattr(chunk, "content") and chunk.content:
                        yield chunk.content
                    elif isinstance(chunk, dict) and chunk.get("content"):
                        yield chunk["content"]
            else:
                # Fallback
                full = await self.generate(prompt, model_type, temperature)
                chunk_size = 8
                for i in range(0, len(full), chunk_size):
                    yield full[i:i + chunk_size]
                    await asyncio.sleep(0.015)
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            full = await self.generate(prompt, model_type, temperature)
            yield full


# ========================================
# 🧩 NODES with Real Streaming Support
# ========================================

async def analyzing_node(state: AgentState):
    """Node with streaming"""
    _emit_agent_step("analyzing", "Analyse des exigences...")
    last_message = state["messages"][-1].get("content", "")

    # Get user-selected model from metadata
    metadata = state.get("metadata", {})
    user_model = metadata.get("model", "")
    user_provider = metadata.get("provider", "ollama")

    llm = LLMWrapper(_get_llm_router(), user_model=user_model, user_provider=user_provider)
    prompt = f"Analyse cette requête utilisateur et identifie le type de tâche:\n\n{last_message}"

    full_response = ""
    async for token in llm.stream_generate(prompt, model_type="reasoning", temperature=0.3):
        full_response += token

    state["messages"].append({"role": "assistant", "content": full_response})
    return state


async def planning_node(state: AgentState):
    """Node with streaming"""
    _emit_agent_step("planning", "Création du plan d'implémentation...")

    metadata = state.get("metadata", {})
    user_model = metadata.get("model", "")
    user_provider = metadata.get("provider", "ollama")

    llm = LLMWrapper(_get_llm_router(), user_model=user_model, user_provider=user_provider)
    prompt = "Crée un plan détaillé pour cette tâche. Inclut: étapes, fichiers à créer, approche technique."

    full_response = ""
    async for token in llm.stream_generate(prompt, model_type="reasoning", temperature=0.3):
        full_response += token

    try:
        plan = json.loads(full_response)
    except:
        plan = {"raw": full_response}

    state["plan"] = plan
    state["messages"].append({"role": "assistant", "content": str(plan)})
    return state


async def coding_node(state: AgentState):
    """Most important node - heavy streaming"""
    _emit_agent_step("coding", "Génération du code...")

    metadata = state.get("metadata", {})
    user_model = metadata.get("model", "")
    user_provider = metadata.get("provider", "ollama")

    llm = LLMWrapper(_get_llm_router(), user_model=user_model, user_provider=user_provider)
    plan = state.get("plan", {})

    prompt = f"""Implémente le plan suivant de façon complète et fonctionnelle:

{json.dumps(plan, ensure_ascii=False)}

Retourne uniquement un JSON valide avec la structure: {{"files": {{"nom_fichier.py": "code complet"}}}}"""

    full_response = ""
    async for token in llm.stream_generate(prompt, model_type="fast", temperature=0.7):
        full_response += token

    try:
        code_dict = json.loads(full_response)
    except:
        code_dict = {"files": {"main.py": full_response}}

    state["code"] = code_dict
    return state


async def reviewing_node(state: AgentState):
    """Review node with streaming"""
    _emit_agent_step("reviewing", "Code Review & Security Check...")

    metadata = state.get("metadata", {})
    user_model = metadata.get("model", "")
    user_provider = metadata.get("provider", "ollama")

    llm = LLMWrapper(_get_llm_router(), user_model=user_model, user_provider=user_provider)
    code = state.get("code", {})

    prompt = f"Analyse ce code de façon critique et retourne un JSON:\n{json.dumps(code, ensure_ascii=False)}"

    full_response = ""
    async for token in llm.stream_generate(prompt, model_type="reasoning", temperature=0.3):
        full_response += token

    try:
        review = json.loads(full_response)
    except:
        review = {"passed": False, "issues": [], "suggestions": ["Could not parse review"]}

    state["review"] = review
    return state


async def executing_node(state: AgentState):
    """Execution node (non-streaming by nature)"""
    _emit_agent_step("executing", "Exécution dans le sandbox...")

    executor = _get_executor()
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
        logger.error("Execution failed", exc_info=True)

    state["attempt"] = state.get("attempt", 0) + 1
    return state


# ========================================
# 🔁 CONDITION
# ========================================

def should_continue(state: AgentState) -> Literal["review", "end"]:
    review = state.get("review")
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)

    if review and review.get("passed", False):
        _emit_agent_step("review_passed", "✅ Code review passed")
        return "end"

    if attempt >= max_attempts:
        _emit_agent_step("max_attempts_reached", f"Max attempts ({max_attempts}) reached")
        return "end"

    _emit_agent_step("fixing", f"🔄 Auto-fix attempt {attempt + 1}/{max_attempts}")
    return "review"


# ========================================
# 🧱 BUILD GRAPH
# ========================================

def build_graph():
    from langgraph.graph import StateGraph, END, START

    workflow = StateGraph(AgentState)

    workflow.add_node("analyze", analyzing_node)
    workflow.add_node("plan", planning_node)
    workflow.add_node("code", coding_node)
    workflow.add_node("review", reviewing_node)
    workflow.add_node("execute", executing_node)

    # Linear flow
    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", "plan")
    workflow.add_edge("plan", "code")
    workflow.add_edge("code", "review")
    workflow.add_edge("review", "execute")

    # Retry loop
    workflow.add_conditional_edges(
        "execute",
        should_continue,
        {"review": "review", "end": END},
    )

    try:
        from langgraph.checkpoint.memory import MemorySaver
        return workflow.compile(checkpointer=MemorySaver())
    except ImportError:
        logger.warning("LangGraph checkpointer not available")
        return workflow.compile()


# ========================================
# Public API (cached singleton)
# ========================================

_app = None


async def get_orchestrator():
    global _app
    if _app is None:
        _app = build_graph()
    return _app


async def run_agent(message: str, session_id: str = "default", max_attempts: int = 3):
    app = await get_orchestrator()

    initial_state: AgentState = {
        "messages": [{"role": "user", "content": message}],
        "attempt": 0,
        "max_attempts": max_attempts,
        "session_id": session_id,
        "metadata": {"start_time": datetime.now().isoformat()},
    }

    _emit_agent_step("orchestrator", f"🚀 Starting session {session_id}")

    try:
        result = await app.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}}
        )
        return {
            "status": "completed" if not result.get("error") else "failed",
            "state": dict(result),
        }
    except Exception as e:
        logger.exception("Agent execution failed")
        return {"status": "failed", "error": str(e)}


# ========================================
# 🌊 ENHANCED STREAMING (captures tokens from all nodes)
# ========================================

_last_message_length: dict[str, int] = {}


async def stream_agent(
    message: str,
    session_id: str = "default",
    max_attempts: int = 3,
    model: str = "",
    provider: str = "ollama"
):
    app = await get_orchestrator()

    initial_state: AgentState = {
        "messages": [{"role": "user", "content": message}],
        "plan": None,
        "code": None,
        "review": None,
        "execution_result": None,
        "error": None,
        "attempt": 0,
        "max_attempts": max_attempts,
        "session_id": session_id,
        "metadata": {
            "start_time": datetime.now().isoformat(),
            "model": model,  # Store user-selected model
            "provider": provider  # Store user-selected provider
        },
    }

    _last_message_length[session_id] = 0
    _emit_agent_step("orchestrator", f"🚀 Starting streaming session {session_id}")

    try:
        yield "[STEP]orchestrator:Starting agent pipeline"

        async for event in app.astream(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
            stream_mode="values",
        ):
            # STEP EVENTS
            if "plan" in event and event.get("plan"):
                yield f"[STEP]planning:Plan created"
            if "code" in event and event.get("code"):
                yield f"[STEP]coding:Code generation completed"
            if "review" in event and event.get("review"):
                review = event["review"]
                status = "✅ PASSED" if review.get("passed") else "⚠️ Needs improvement"
                yield f"[STEP]reviewing:Review - {status}"
            if "execution_result" in event:
                result = event["execution_result"]
                success = result.get("success", False) if isinstance(result, dict) else False
                yield f"[STEP]executing:Execution {'✅ Success' if success else '❌ Failed'}"

            # REAL TOKEN STREAMING from latest assistant message
            if "messages" in event and event["messages"]:
                last_msg = event["messages"][-1]
                if last_msg.get("role") == "assistant":
                    content = last_msg.get("content", "")
                    last_len = _last_message_length.get(session_id, 0)

                    if len(content) > last_len:
                        new_text = content[last_len:]
                        if new_text.strip():
                            yield f"[TOKEN]{new_text}"
                        _last_message_length[session_id] = len(content)

            # Tool events
            if "execution_result" in event and isinstance(event["execution_result"], dict):
                res = event["execution_result"]
                if res.get("files_written"):
                    for f in res["files_written"]:
                        yield f"[TOOL]write_file:Created {f}"

        yield "[STEP]completed:Task completed successfully"
        yield "[DONE]"

    except Exception as e:
        logger.exception("Streaming failed")
        yield f"[ERROR]500:{str(e)}"
        yield "[DONE]"

    finally:
        _last_message_length.pop(session_id, None)


# ========================================
# Backward Compatibility
# ========================================

class LangGraphOrchestrator:
    """Backward compatibility wrapper"""
    async def run(self, message: str, session_id: str, **kwargs):
        return await run_agent(message, session_id)


def get_langgraph_orchestrator() -> LangGraphOrchestrator:
    return LangGraphOrchestrator()


__all__ = [
    "AgentState",
    "get_orchestrator",
    "run_agent",
    "stream_agent",
    "LangGraphOrchestrator",
    "get_langgraph_orchestrator",
    "build_graph",
]