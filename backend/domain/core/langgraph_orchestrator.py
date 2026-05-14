"""
backend/domain/core/langgraph_orchestrator.py
Migration complète vers LangGraph officiel + Real Token Streaming
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
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


def _get_llm_router():
    """Lazy init of LLM router."""
    global _llm_router
    if _llm_router is None:
        from backend.infrastructure.llm_router import LLMRouter
        _llm_router = LLMRouter()
    return _llm_router


_executor = None
_checkpointer = None
_checkpointer_ready = threading.Event()


def _get_executor():
    """Lazy init of code executor."""
    global _executor
    if _executor is None:
        from backend.infrastructure.code_execution import CodeExecutionService
        _executor = CodeExecutionService()
    return _executor


def _get_checkpointer():
    """Persistent checkpointing with async SQLite (properly initialized)."""
    global _checkpointer, _checkpointer_ready

    if _checkpointer is not None:
        return _checkpointer

    from pathlib import Path as _Path
    db_path = _Path("data/checkpoints.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Try async SqliteSaver with proper async context manager initialization
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        import asyncio

        # Must be run in an async context - use a flag to ensure one-time init
        def _init():
            global _checkpointer, _checkpointer_ready
            if _checkpointer is None:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    saver = loop.run_until_complete(
                        AsyncSqliteSaver.from_conn_string(str(db_path)).__aenter__()
                    )
                    _checkpointer = saver
                    logger.info(f"Async SQLite checkpointing enabled: {db_path}")
                except Exception as e:
                    logger.warning(f"Async SQLite checkpointing failed: {e}")

        t = threading.Thread(target=_init, daemon=True)
        t.start()
        t.join(timeout=5)

        if _checkpointer is not None:
            return _checkpointer

    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: in-memory
    from langgraph.checkpoint.memory import MemorySaver
    _checkpointer = MemorySaver()
    logger.warning("SQLite checkpointing unavailable -> Using in-memory checkpointing")
    return _checkpointer


def _emit_agent_step(phase: str, message: str):
    """Emit agent step event, stripping non-ASCII for Windows console."""
    try:
        # Strip non-ASCII chars for Windows console (cp1252)
        try:
            message.encode('cp1252').decode('cp1252')
        except (UnicodeEncodeError, UnicodeDecodeError):
            message = message.encode('ascii', 'replace').decode('ascii')
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

    metadata = state.get("metadata", {})
    user_model = metadata.get("model", "")
    user_provider = metadata.get("provider", "ollama")

    llm = LLMWrapper(_get_llm_router(), user_model=user_model, user_provider=user_provider)
    messages = state.get("messages", [])
    user_message = messages[0].get("content", "") if messages else ""

    prompt = (
        f"User request: {user_message}\n\n"
        "Classify the task type and respond with ONLY valid JSON:\n"
        '{"task_type": "code|reasoning|general", "summary": "brief description"}\n'
        "No markdown, no explanation - only JSON."
    )

    full_response = ""
    async for token in llm.stream_generate(prompt, model_type="reasoning", temperature=0.3):
        full_response += token

    # Extract JSON
    response_clean = full_response.strip()
    if response_clean.startswith("```"):
        lines = response_clean.split("\n")
        response_clean = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        response_clean = response_clean.strip()

    state["messages"].append({"role": "assistant", "content": full_response})
    return state


async def planning_node(state: AgentState):
    """Node with streaming"""
    _emit_agent_step("planning", "Creation du plan d'implementation...")

    metadata = state.get("metadata", {})
    user_model = metadata.get("model", "")
    user_provider = metadata.get("provider", "ollama")

    llm = LLMWrapper(_get_llm_router(), user_model=user_model, user_provider=user_provider)
    messages = state.get("messages", [])
    user_message = messages[0].get("content", "") if messages else ""

    # Force JSON-only output - no commentary, no markdown
    prompt = (
        f"User request: {user_message}\n\n"
        "Create a detailed implementation plan as VALID JSON ONLY. "
        "No markdown, no code blocks, no explanations - ONLY raw JSON.\n"
        'Structure: {"steps": [{"description": "...", "file": "...", "approach": "..."}], "files": {"filename.py": "brief description"}}\n'
        "Respond with ONLY the JSON object."
    )

    full_response = ""
    async for token in llm.stream_generate(prompt, model_type="reasoning", temperature=0.3):
        full_response += token

    # Extract JSON from response (strip markdown code blocks if present)
    response_clean = full_response.strip()
    if response_clean.startswith("```"):
        # Remove markdown code block syntax
        lines = response_clean.split("\n")
        response_clean = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        response_clean = response_clean.strip()

    try:
        plan = json.loads(response_clean)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_clean)
        if json_match:
            try:
                plan = json.loads(json_match.group(0))
            except:
                plan = {"raw": response_clean, "steps": [], "files": {}}
        else:
            plan = {"raw": response_clean, "steps": [], "files": {}}

    # Clean plan - remove thinking/raw content that would pollute the prompt
    plan_clean = {k: v for k, v in plan.items() if k not in ("raw", "thinking", "analysis")}
    state["plan"] = plan_clean
    state["messages"].append({"role": "assistant", "content": str(plan_clean)})
    return state


async def coding_node(state: AgentState):
    """Most important node - heavy streaming"""
    _emit_agent_step("coding", "Generation du code...")

    metadata = state.get("metadata", {})
    user_model = metadata.get("model", "")
    user_provider = metadata.get("provider", "ollama")

    llm = LLMWrapper(_get_llm_router(), user_model=user_model, user_provider=user_provider)
    messages = state.get("messages", [])
    user_message = messages[0].get("content", "") if messages else ""
    plan = state.get("plan", {})
    plan_clean = {k: v for k, v in plan.items() if k not in ("raw", "thinking", "analysis")}

    prompt = (
        f"User request: {user_message}\n\n"
        f"Implementation plan: {json.dumps(plan_clean, ensure_ascii=False)}\n\n"
        "IMPORTANT: Return ONLY valid JSON. No markdown, no explanations.\n"
        'Format: {"files": {"filename.py": "python code here - NO comments, NO docstrings, ONLY executable code"}}\n'
        "Write complete, working Python code in the files. No prose, no comments, no markdown."
    )

    full_response = ""
    async for token in llm.stream_generate(prompt, model_type="fast", temperature=0.3):
        full_response += token

    import re
    import textwrap

    response_clean = full_response.strip()
    response_clean = re.sub(r'^```(?:json|python)?\s*', '', response_clean, flags=re.MULTILINE)
    response_clean = re.sub(r'\s*```$', '', response_clean)
    response_clean = response_clean.strip()

    code_dict = None

    # Strategy 1: Try direct JSON parse
    if code_dict is None:
        try:
            candidate = json.loads(response_clean)
            if isinstance(candidate, dict) and "files" in candidate:
                for fname, fcontent in candidate["files"].items():
                    if not isinstance(fcontent, str):
                        raise ValueError(f"File {fname} content is not a string")
                code_dict = candidate
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            pass

    # Strategy 2: Find JSON object with "files" key
    if code_dict is None:
        json_matches = re.findall(r'\{[\s\S]*?\}', response_clean)
        for match in json_matches:
            try:
                candidate = json.loads(match)
                if isinstance(candidate, dict) and "files" in candidate:
                    files = candidate["files"]
                    if isinstance(files, dict) and all(isinstance(v, str) for v in files.values()):
                        valid_files = {}
                        for fname, fcontent in files.items():
                            try:
                                compile(fcontent, fname, 'exec')
                                valid_files[fname] = fcontent
                            except SyntaxError:
                                try:
                                    fixed = textwrap.dedent(fcontent).strip()
                                    compile(fixed, fname, 'exec')
                                    valid_files[fname] = fixed + '\n'
                                except SyntaxError:
                                    pass
                        if valid_files:
                            code_dict = {"files": valid_files}
                            break
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

    # Strategy 3: Extract python code blocks and normalize
    if code_dict is None:
        py_blocks = re.findall(r'```python\s*([\s\S]*?)```', response_clean)
        if py_blocks:
            files = {}
            for i, block in enumerate(py_blocks):
                block = block.strip()
                if not block:
                    continue
                lines = block.expandtabs(4).split('\n')
                non_empty = [l for l in lines if l.strip()]
                if not non_empty:
                    continue
                min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
                fixed_lines = []
                for line in lines:
                    if line.strip():
                        fixed_lines.append(line[min_indent:])
                    else:
                        fixed_lines.append('')
                normalized = '\n'.join(fixed_lines).strip()
                try:
                    compile(normalized, f'file_{i+1}.py', 'exec')
                except SyntaxError:
                    try:
                        normalized = textwrap.dedent(normalized).strip()
                        compile(normalized, f'file_{i+1}.py', 'exec')
                    except SyntaxError:
                        normalized = textwrap.dedent(normalized).strip()
                if normalized.strip():
                    files[f"file_{i+1}.py"] = normalized + '\n'
            if files:
                code_dict = {"files": files}

    # Strategy 4: Direct Python code detection
    if code_dict is None:
        py_start = re.search(r'^def\s+\w+|^\s*def\s+\w+|^class\s+\w+|^import\s+|^from\s+',
                            response_clean, re.MULTILINE)
        if py_start:
            code_dict = {"files": {"main.py": response_clean.strip()}}

    # Fallback
    if code_dict is None:
        code_dict = {"files": {"main.py": response_clean}}

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
        _emit_agent_step("review_passed", "[OK] Code review passed")
        return "end"

    if attempt >= max_attempts:
        _emit_agent_step("max_attempts_reached", f"Max attempts ({max_attempts}) reached")
        return "end"

    _emit_agent_step("fixing", f"Auto-fix attempt {attempt + 1}/{max_attempts}")
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

    checkpointer = _get_checkpointer()
    return workflow.compile(checkpointer=checkpointer)


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

    _emit_agent_step("orchestrator", f"Starting session {session_id}")

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
    _emit_agent_step("orchestrator", f"Starting streaming session {session_id}")

    try:
        yield "[STEP]orchestrator:Starting agent pipeline"

        async for event in app.astream(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
            stream_mode="values",
        ):
            # STEP EVENTS (detected in full state snapshots)
            plan_val = event.get("plan")
            if plan_val:
                yield "[STEP]planning:Plan created"
            code_val = event.get("code")
            if code_val:
                yield "[STEP]coding:Code generation completed"
            review_val = event.get("review")
            if review_val:
                status = "PASSED" if review_val.get("passed") else "Needs improvement"
                yield f"[STEP]reviewing:Review - {status}"
            exec_val = event.get("execution_result")
            if exec_val:
                success = exec_val.get("success", False) if isinstance(exec_val, dict) else False
                yield f"[STEP]executing:Execution {'OK' if success else 'FAILED'}"

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
            exec_result = event.get("execution_result")
            if exec_result and isinstance(exec_result, dict):
                res = exec_result
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