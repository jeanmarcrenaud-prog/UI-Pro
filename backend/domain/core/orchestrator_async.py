"""
backend/domain/core/orchestrator_async.py
Orchestrateur Agentic principal avec LangGraph (Version 2026)

Source of truth pour l'orchestration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Literal

from backend.domain.settings import settings

# Workspace constant for test compatibility
WORKSPACE = settings.workspace_path

logger = logging.getLogger(__name__)


# Lazy imports to avoid circular imports
def _get_executor():
    from backend.infrastructure.code_execution import CodeExecutionService

    return CodeExecutionService


def _get_llm_router():
    from backend.infrastructure.llm_router import get_llm_router

    return get_llm_router


def _get_tool_registry():
    from backend.infrastructure.tools import ToolManager

    return ToolManager


def _get_metrics_manager():
    from backend.domain.core.metrics import MetricsManager

    return MetricsManager


def _emit_agent_step(phase: str, message: str):
    try:
        from backend.domain.core.events import emit_agent_step

        emit_agent_step(phase, message)
    except ImportError:
        pass


# ====================== STATE ======================
from backend.domain.core.langgraph.state import AgentState

# ====================== LLM WRAPPER ======================
class LLMWrapper:
    """Wrapper around LLMRouter pour generate_structured"""

    def __init__(self, router):
        self.router = router

    async def generate(
        self, prompt: str, model_type: str = "fast", temperature: float = 0.7
    ) -> str:
        """Generate text response."""
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(
                None, lambda: self.router.generate(prompt, model_type)
            ),
            timeout=float(settings.llm_timeout),
        )

    async def generate_structured(
        self,
        prompt: str,
        model_type: str = "reasoning",
        output_schema: dict | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Generate structured JSON response."""
        # Add schema hint to prompt if provided
        if output_schema:
            schema_hint = f"\n\nRéponds uniquement en JSON avec ce format: {json.dumps(output_schema)}"
            prompt = prompt + schema_hint

        response = await self.generate(prompt, model_type, temperature)

        # Parse JSON safely
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                json_lines = [
                    l
                    for l in lines
                    if not l.startswith("```") and not l.startswith("json")
                ]
                cleaned = "\n".join(json_lines)
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass

            logger.warning("Failed to parse JSON from LLM response, returning raw")
            return {"raw": response[:500], "error": "invalid_json"}


# ====================== NODES ======================
async def analyzing_node(state: AgentState, llm: LLMWrapper) -> AgentState:
    """Node: Analyze user request"""
    _emit_agent_step("analyzing", "Analyse des exigences...")
    last_message = state.get("messages", [{}])[-1].get("content", "")

    response = await llm.generate(
        prompt=f"Analyse cette requête utilisateur et identifie le type de tâche:\n\n{last_message}",
        model_type="reasoning",
        temperature=0.3,
    )

    state["messages"].append({"role": "assistant", "content": response})
    return state


async def planning_node(state: AgentState, llm: LLMWrapper) -> AgentState:
    """Node: Create implementation plan"""
    _emit_agent_step("planning", "Création du plan d'implémentation...")

    plan = await llm.generate_structured(
        prompt="Crée un plan détaillé pour cette tâche. Inclut: étapes, fichiers à créer, approche technique.",
        model_type="reasoning",
        output_schema={"steps": list, "files": list, "approach": str},
    )

    state["plan"] = plan
    state["messages"].append({"role": "assistant", "content": str(plan)})
    return state


async def coding_node(state: AgentState, llm: LLMWrapper) -> AgentState:
    """Node: Generate code"""
    _emit_agent_step("coding", "Génération du code...")

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


async def review_node(state: AgentState, llm: LLMWrapper) -> AgentState:
    """Node: Code review (quality, security, best practices)"""
    _emit_agent_step("reviewing", "Code Review...")

    code = state.get("code", {})
    review = await llm.generate_structured(
        prompt=f"Analyse ce code de façon critique:\n{json.dumps(code)}\nRetourne: {{'passed': bool, 'issues': list, 'suggestions': list}}",
        model_type="reasoning",
        output_schema={"passed": bool, "issues": list, "suggestions": list},
    )

    state["review"] = review
    return state


async def execute_node(state: AgentState, executor: Any) -> AgentState:
    """Node: Execute code in sandbox"""
    _emit_agent_step("executing", "Exécution dans le sandbox...")

    code = state.get("code", {})
    files = code.get("files", {})

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
    except Exception as e:
        state["error"] = str(e)
        state["execution_result"] = {"success": False, "error": str(e)}
        logger.error("Execution failed", exc_info=True)

    state["attempt"] += 1
    return state


# ====================== CONDITIONAL EDGES ======================
def should_fix_code(state: AgentState) -> Literal["coding", "end"]:
    """Determine if we should retry the code → review → execute cycle"""
    review = state.get("review")
    execution_result = state.get("execution_result")
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)

    # Priorité 1: échec d'exécution + tentatives épuisées → STOP
    if execution_result is not None:
        if not execution_result.get("success", False) and attempt >= max_attempts:
            error_msg = execution_result.get("error", "unknown error")
            _emit_agent_step("execution_failed", f"Execution failed (max {max_attempts} tentatives): {error_msg[:80]}")
            return "end"

    # Priorité 2: échec d'exécution + tentatives restantes → auto-fix
    if execution_result is not None:
        if not execution_result.get("success", False):
            error_msg = execution_result.get("error", "unknown error")
            _emit_agent_step("fixing", f"Auto-fix execution ({attempt + 1}/{max_attempts}): {error_msg[:60]}")
            return "coding"

    # Priorité 3: review passée + execution OK → STOP
    if review and review.get("passed", False):
        return "end"

    # Priorité 4: max attempts atteint → STOP
    if attempt >= max_attempts:
        return "end"

    next_attempt = attempt + 1
    _emit_agent_step("fixing", f"Auto-fix tentative {next_attempt}/{max_attempts}")
    return "coding"


# ====================== ORCHESTRATOR ======================
class OrchestratorAsync:
    """
    Orchestrateur principal basé sur LangGraph.
    Gère le cycle: analyze → plan → code → review → execute → (fix loop)
    """

    def __init__(
        self,
        llm_router=None,
        executor=None,
        tool_registry=None,
        metrics=None,
    ):
        self._llm_router = llm_router
        self._executor = executor
        self._tool_registry = tool_registry
        self._metrics = metrics
        self._llm = None
        self._graph = None

    @property
    def llm_router(self):
        if self._llm_router is None:
            self._llm_router = _get_llm_router()()
        return self._llm_router

    @property
    def executor(self):
        if self._executor is None:
            self._executor = _get_executor()()
        return self._executor

    @property
    def tool_registry(self):
        if self._tool_registry is None:
            self._tool_registry = _get_tool_registry()()
        return self._tool_registry

    @property
    def metrics(self):
        if self._metrics is None:
            self._metrics = _get_metrics_manager()()
        return self._metrics

    @property
    def llm(self):
        if self._llm is None:
            self._llm = LLMWrapper(self.llm_router)
        return self._llm

    def _build_graph(self):
        """Build LangGraph workflow (lazy build)"""
        try:
            from langgraph.checkpoint.memory import MemorySaver
            from langgraph.graph import END, START, StateGraph

            workflow = StateGraph(AgentState)

            # Add nodes
            workflow.add_node("analyzing", lambda s: asyncio.run(analyzing_node(s, self.llm)))  # type: ignore[arg-type]
            workflow.add_node("planning", lambda s: asyncio.run(planning_node(s, self.llm)))  # type: ignore[arg-type]
            workflow.add_node("coding", lambda s: asyncio.run(coding_node(s, self.llm)))  # type: ignore[arg-type]
            workflow.add_node("reviewing", lambda s: asyncio.run(review_node(s, self.llm)))  # type: ignore[arg-type]
            workflow.add_node("executing", lambda s: asyncio.run(execute_node(s, self.executor)))  # type: ignore[arg-type]

            # Main flow
            workflow.add_edge(START, "analyzing")
            workflow.add_edge("analyzing", "planning")
            workflow.add_edge("planning", "coding")
            workflow.add_edge("coding", "reviewing")
            workflow.add_edge("reviewing", "executing")

            # Auto-fix loop
            workflow.add_conditional_edges(
                "executing", should_fix_code, {"coding": "coding", "end": END}
            )

            checkpointer = MemorySaver()
            return workflow.compile(checkpointer=checkpointer)

        except ImportError:
            logger.warning("LangGraph not installed, using fallback orchestrator")
            return None

    @property
    def graph(self):
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    async def run(
        self, message: str, session_id: str, stream_mode: str = "values"
    ) -> dict[str, Any]:
        """
        Execute the orchestrator pipeline.

        Args:
            message: User message/task
            session_id: Session identifier
            stream_mode: Streaming mode (not used in fallback)

        Returns:
            dict with status, data, errors
        """
        start_time = time.time()

        try:
            # Use LangGraph if available
            if self.graph is not None:
                return await self._run_langgraph(message, session_id)
            else:
                # Fallback to sequential pipeline
                return await self._run_fallback(message, session_id)

        except Exception as e:
            logger.exception("Orchestrator error")
            self.metrics.track_error("orchestrator", str(e))
            return {
                "status": "failed",
                "error": str(e),
            }

    async def _run_langgraph(self, message: str, session_id: str) -> dict[str, Any]:
        """Run using LangGraph"""

        initial_state: AgentState = {
            "messages": [{"role": "user", "content": message}],
            "session_id": session_id,
            "attempt": 0,
            "max_attempts": 3,
            "metadata": {"start_time": datetime.now().isoformat()},
        }

        _emit_agent_step("orchestrator", f"Session démarrée: {session_id}")

        results = []
        async for event in self.graph.astream(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
            stream_mode="values",
        ):
            results.append(event)

        return {
            "status": "completed",
            "events": results,
        }

    async def _run_fallback(self, message: str, session_id: str) -> dict[str, Any]:
        """Fallback sequential pipeline when LangGraph not available"""
        state: AgentState = {
            "messages": [{"role": "user", "content": message}],
            "session_id": session_id,
            "attempt": 0,
            "max_attempts": 3,
            "metadata": {"start_time": datetime.now().isoformat()},
        }

        _emit_agent_step("orchestrator", f"Session démarrée (fallback): {session_id}")

        # Sequential execution
        state = await analyzing_node(state, self.llm)
        state = await planning_node(state, self.llm)
        state = await coding_node(state, self.llm)
        state = await review_node(state, self.llm)
        state = await execute_node(state, self.executor)

        # Auto-fix loop
        while should_fix_code(state) == "coding" and state.get(
            "attempt", 0
        ) < state.get("max_attempts", 3):
            state = await coding_node(state, self.llm)
            state = await review_node(state, self.llm)
            state = await execute_node(state, self.executor)

        return {
            "status": "completed" if not state.get("error") else "failed",
            "state": dict(state),
        }


# ====================== FACTORY ======================
_orchestrator: OrchestratorAsync | None = None


async def get_orchestrator() -> OrchestratorAsync:
    """Factory pour injection de dépendances"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAsync()
    return _orchestrator


__all__ = ["AgentState", "OrchestratorAsync", "get_orchestrator"]
