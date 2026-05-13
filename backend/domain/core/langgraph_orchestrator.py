"""
backend/domain/core/langgraph_orchestrator.py
Migration complète vers LangGraph officiel (depuis orchestrator_async.py)

Conserve: AgentState, nodes, boucle retry, executor, LLM router, streaming
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Literal, Optional

from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


# ========================================
# 🧠 STATE (mapping exact de AgentState)
# ========================================

class AgentState(TypedDict, total=False):
    """État persistant du graphe LangGraph - mapping 1:1 de l'ancien AgentState"""
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
# 🔧 Lazy imports (évite circular imports)
# ========================================

def _get_llm_router():
    from backend.infrastructure.llm_router import get_llm_router
    return get_llm_router()


def _get_executor():
    from backend.infrastructure.code_execution import CodeExecutor
    return CodeExecutor()


def _emit_agent_step(phase: str, message: str):
    try:
        from backend.domain.core.events import emit_agent_step
        emit_agent_step(phase, message)
    except (ImportError, Exception):
        pass


# ========================================
# 🧩 LLM Wrapper (reprend LLMWrapper de l'ancien)
# ========================================

class LLMWrapper:
    """Wrapper autour de LLMRouter pour generate_structured"""

    def __init__(self, router):
        self.router = router

    async def generate(
        self,
        prompt: str,
        model_type: str = "fast",
        temperature: float = 0.7
    ) -> str:
        """Generate text response."""
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, lambda: self.router.generate(prompt, model_type)),
            timeout=120.0
        )

    async def generate_structured(
        self,
        prompt: str,
        model_type: str = "reasoning",
        output_schema: Optional[dict] = None,
        temperature: float = 0.3
    ) -> dict[str, Any]:
        """Generate structured JSON response."""
        if output_schema:
            schema_hint = f"\n\nRéponds uniquement en JSON avec ce format: {json.dumps(output_schema)}"
            prompt = prompt + schema_hint

        response = await self.generate(prompt, model_type, temperature)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                json_lines = [l for l in lines if not l.startswith("```") and not l.startswith("json")]
                cleaned = "\n".join(json_lines)
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass
            logger.warning("Failed to parse JSON from LLM response, returning raw")
            return {"raw": response[:500], "error": "invalid_json"}


# ========================================
# 🧩 NODES (reprend 1:1 l'ancien code)
# ========================================

async def analyzing_node(state: AgentState) -> AgentState:
    """Node: Analyze user request"""
    _emit_agent_step("analyzing", "Analyse des exigences...")
    last_message = state.get("messages", [{}])[-1].get("content", "")

    router = _get_llm_router()()
    llm = LLMWrapper(router)

    response = await llm.generate(
        prompt=f"Analyse cette requête utilisateur et identifie le type de tâche:\n\n{last_message}",
        model_type="reasoning",
        temperature=0.3,
    )

    state["messages"].append({"role": "assistant", "content": response})
    return state


async def planning_node(state: AgentState) -> AgentState:
    """Node: Create implementation plan"""
    _emit_agent_step("planning", "Création du plan d'implémentation...")

    router = _get_llm_router()()
    llm = LLMWrapper(router)

    plan = await llm.generate_structured(
        prompt="Crée un plan détaillé pour cette tâche. Inclut: étapes, fichiers à créer, approche technique.",
        model_type="reasoning",
        output_schema={"steps": list, "files": list, "approach": str},
    )

    state["plan"] = plan
    state["messages"].append({"role": "assistant", "content": str(plan)})
    return state


async def coding_node(state: AgentState) -> AgentState:
    """Node: Generate code"""
    _emit_agent_step("coding", "Génération du code...")

    router = _get_llm_router()()
    llm = LLMWrapper(router)

    plan = state.get("plan", {})
    code_dict = await llm.generate_structured(
        prompt=f"""Implémente le plan suivant de façon complète:

{json.dumps(plan)}

Retourne uniquement un objet JSON: {{"files": {{"nom_fichier.py": "code complet"}}}}""",
        model_type="fast",
        output_schema={"files": dict},
    )

    state["code"] = code_dict
    return state


async def reviewing_node(state: AgentState) -> AgentState:
    """Node: Code review (quality, security, best practices)"""
    _emit_agent_step("reviewing", "Code Review...")

    router = _get_llm_router()()
    llm = LLMWrapper(router)

    code = state.get("code", {})
    review = await llm.generate_structured(
        prompt=f"Analyse ce code de façon critique:\n{json.dumps(code)}\nRetourne: {{'passed': bool, 'issues': list, 'suggestions': list}}",
        model_type="reasoning",
        output_schema={"passed": bool, "issues": list, "suggestions": list},
    )

    state["review"] = review
    return state


async def executing_node(state: AgentState) -> AgentState:
    """Node: Execute code in sandbox"""
    _emit_agent_step("executing", "Exécution dans le sandbox...")

    executor = _get_executor()()
    code = state.get("code", {})
    files = code.get("files", {})

    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: executor.run(files)),
            timeout=60.0
        )
        state["execution_result"] = result
    except Exception as e:
        state["error"] = str(e)
        logger.error("Execution failed", exc_info=True)

    state["attempt"] += 1
    return state


# ========================================
# 🔁 CONDITION (boucle retry - identique à l'ancien)
# ========================================

def should_continue(state: AgentState) -> Literal["coding", "end"]:
    """Détermine si on continue la boucle code → review → execute"""
    review = state.get("review")
    if review and review.get("passed", False):
        return "end"
    if state.get("attempt", 0) >= state.get("max_attempts", 3):
        return "end"

    attempt = state.get("attempt", 0) + 1
    max_attempts = state.get("max_attempts", 3)
    _emit_agent_step("fixing", f"Auto-fix tentative {attempt}/{max_attempts}")
    return "coding"


# ========================================
# 🧱 BUILD GRAPH (LangGraph officiel)
# ========================================

def build_graph():
    """Construit le graphe LangGraph avec la structure officielle"""
    from langgraph.graph import StateGraph, END, START

    workflow = StateGraph(AgentState)

    workflow.add_node("analyze", analyzing_node)
    workflow.add_node("plan", planning_node)
    workflow.add_node("code", coding_node)
    workflow.add_node("review", reviewing_node)
    workflow.add_node("execute", executing_node)

    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", "plan")
    workflow.add_edge("plan", "code")
    workflow.add_edge("code", "review")
    workflow.add_edge("review", "execute")

    workflow.add_conditional_edges(
        "execute",
        should_continue,
        {
            "coding": "code",
            "end": END,
        }
    )

    try:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)
    except ImportError:
        return workflow.compile()


# ========================================
# 🚀 ORCHESTRATOR PUBLIC
# ========================================

_app: Optional[Any] = None


async def get_orchestrator():
    """Factory pour obtenir le graphe LangGraph compilé"""
    global _app
    if _app is None:
        _app = build_graph()
    return _app


# ========================================
# ▶️ EXECUTION SIMPLE (non-streaming)
# ========================================

async def run_agent(
    message: str,
    session_id: str = "default",
    max_attempts: int = 3
) -> dict[str, Any]:
    """
    Exécute l'agent de façon synchrone.
    
    Args:
        message: Message utilisateur
        session_id: ID de session
        max_attempts: Nombre max de tentatives de retry
    
    Returns:
        dict avec status, state, events
    """
    app = await get_orchestrator()

    state: AgentState = {
        "messages": [{"role": "user", "content": message}],
        "plan": None,
        "code": None,
        "review": None,
        "execution_result": None,
        "error": None,
        "attempt": 0,
        "max_attempts": max_attempts,
        "session_id": session_id,
        "metadata": {"start_time": datetime.now().isoformat()},
    }

    _emit_agent_step("orchestrator", f"Session démarrée: {session_id}")

    try:
        result = await app.ainvoke(
            state,
            config={"configurable": {"thread_id": session_id}}
        )
        return {
            "status": "completed" if not result.get("error") else "failed",
            "state": dict(result),
        }
    except Exception as e:
        logger.exception("Agent execution failed")
        return {
            "status": "failed",
            "error": str(e),
        }


# ========================================
# 🌊 STREAMING (compatible WebSocket)
# ========================================

async def stream_agent(
    message: str,
    session_id: str = "default",
    max_attempts: int = 3
):
    """
    Exécute l'agent en mode streaming.
    
    Yields:
        dict avec step, node, data pour streaming WebSocket
    
    Usage WebSocket:
        async for step in stream_agent(message, session_id):
            await ws.send_json(step)
    """
    app = await get_orchestrator()

    state: AgentState = {
        "messages": [{"role": "user", "content": message}],
        "plan": None,
        "code": None,
        "review": None,
        "execution_result": None,
        "error": None,
        "attempt": 0,
        "max_attempts": max_attempts,
        "session_id": session_id,
        "metadata": {"start_time": datetime.now().isoformat()},
    }

    _emit_agent_step("orchestrator", f"Session streaming: {session_id}")

    try:
        from langgraph.types import StreamMode
        async for event in app.astream(
            state,
            config={"configurable": {"thread_id": session_id}},
            stream_mode=StreamMode("values"),
        ):
            yield {
                "step": "node_output",
                "data": event,
            }
    except Exception as e:
        logger.exception("Streaming failed")
        yield {
            "step": "error",
            "error": str(e),
        }


# ========================================
# 📊 Méthodes utilitaires
# ========================================

async def get_agent_status(session_id: str) -> dict[str, Any]:
    """Récupère le statut d'une session (si checkpointer configuré)"""
    try:
        app = await get_orchestrator()
        from langgraph.checkpoint.memory import MemorySaver
        config = {"configurable": {"thread_id": session_id}}
        return {"status": "active", "session_id": session_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ========================================
# 🔄 Wrapper compatible avec l'ancien OrchestratorAsync
# ========================================

class LangGraphOrchestrator:
    """
    Wrapper compatible avec l'ancien OrchestratorAsync.
    Utilise LangGraph officiel en interne.
    """

    def __init__(self):
        self._graph = None

    @property
    def graph(self):
        if self._graph is None:
            self._graph = build_graph()
        return self._graph

    async def run(
        self,
        message: str,
        session_id: str,
        stream_mode: str = "values"
    ) -> dict[str, Any]:
        """Compatible avec l'ancienne interface"""
        return await run_agent(message, session_id)


async def get_langgraph_orchestrator() -> LangGraphOrchestrator:
    """Factory pour compatibilité arrière"""
    return LangGraphOrchestrator()


__all__ = [
    "AgentState",
    "build_graph",
    "get_orchestrator",
    "run_agent",
    "stream_agent",
    "LangGraphOrchestrator",
    "get_langgraph_orchestrator",
]