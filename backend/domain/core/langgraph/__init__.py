"""LangGraph orchestrator - main entry point.

Refactored into submodules:
- state:        AgentState TypedDict
- nodes:        Pipeline nodes (analyze, plan, code, review, execute)
- checkpointer: Async SQLite checkpointing
- streaming:    Token streaming pipeline
- llm_wrapper:  LLM wrapper with streaming
- code_extractor: Python code extraction from LLM responses
"""

from __future__ import annotations

import logging
from datetime import datetime

from .checkpointer import _get_checkpointer
from .state import AgentState

logger = logging.getLogger(__name__)

_llm_router = None


def _get_llm_router():
    global _llm_router
    if _llm_router is None:
        from backend.infrastructure.llm_router import LLMRouter

        _llm_router = LLMRouter()
    return _llm_router


# ========================================
# Graph Builder
# ========================================


def build_graph():
    from langgraph.graph import END, START, StateGraph

    from .nodes import (
        analyzing_node,
        coding_node,
        executing_node,
        planning_node,
        reviewing_node,
        should_continue,
    )

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
        {"review": "review", "end": END},
    )

    checkpointer = _get_checkpointer()
    return workflow.compile(checkpointer=checkpointer)


# ========================================
# Public API
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

    try:
        result = await app.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
        )
        return {
            "status": "completed" if not result.get("error") else "failed",
            "state": dict(result),
        }
    except Exception as e:
        logger.exception("Agent execution failed")
        return {"status": "failed", "error": str(e)}


# ========================================
# Backward Compatibility
# ========================================


class LangGraphOrchestrator:
    async def run(self, message: str, session_id: str, **kwargs):
        return await run_agent(message, session_id)


def get_langgraph_orchestrator() -> LangGraphOrchestrator:
    return LangGraphOrchestrator()


__all__ = [
    "AgentState",
    "LangGraphOrchestrator",
    "build_graph",
    "get_langgraph_orchestrator",
    "get_orchestrator",
    "run_agent",
    "stream_agent",
]


# Lazy import to avoid circular deps
def __getattr__(name):
    if name == "stream_agent":
        from .streaming import stream_agent

        return stream_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
