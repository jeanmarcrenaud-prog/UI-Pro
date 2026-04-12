# 🚀 Async Orchestrator - PRO VERSION + Auto-Fix
"""
Refactored async orchestrator with proper typing and robust error handling.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import asyncio

from core.state_manager import StateManager
from core.executor import CodeExecutor
from models.llm_router import LLMRouter

# Try to import centralized prompts
try:
    from core.prompts import (
        PLANNER_PROMPT,
        ARCHITECT_PROMPT,
        CODER_PROMPT,
        REVIEWER_PROMPT,
        FIX_PROMPT,
    )
except ImportError:
    PLANNER_PROMPT = None
    ARCHITECT_PROMPT = None
    CODER_PROMPT = None
    REVIEWER_PROMPT = None
    FIX_PROMPT = None

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResult:
    """Result dataclass for orchestrator output."""
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status,
            **self.data,
            "errors": self.errors,
        }


class Orchestrator:
    """Async orchestrator with clean pipeline and auto-fix loop."""

    def __init__(
        self,
        state_manager: StateManager | None = None,
        router: LLMRouter | None = None,
        code_executor: CodeExecutor | None = None,
    ) -> None:
        self.state_manager = state_manager or StateManager()
        self.router = router or LLMRouter()
        self.executor = code_executor or CodeExecutor()
        self.state = None

    async def run(self, task: str) -> dict[str, Any]:
        """Main entry point for the orchestrator pipeline."""
        start_time = time.time()

        try:
            # ================= STATE =================
            self.state = self.state_manager.create(task_id=task[:8])
            self.state.task = task
            self.state.status = "running"

            logger.info("🚀 Starting pipeline: %s", task)

            # ================= STEP 1: PARALLEL =================
            logger.info("Step 1: Planning + Memory")

            plan, memory = await asyncio.gather(
                self._planner(task),
                self._memory(task),
            )

            self.state.plan = plan
            self.state.memory = memory

            # ================= STEP 2: ARCHITECT =================
            logger.info("Step 2: Architecture")

            architecture = await self._architect(task, plan)
            self.state.architecture = architecture

            # ================= STEP 3: CODER =================
            logger.info("Step 3: Code generation")

            code = await self._coder(task, architecture)
            self.state.code = code

            # ================= STEP 4: REVIEW =================
            logger.info("Step 4: Review")

            review = await self._reviewer(code)
            self.state.review = review

            # ================= STEP 5: TEST =================
            logger.info("Step 5: Test")

            tests = await self._runner(code)
            self.state.tests = tests

            # ================= FINAL =================
            duration = int((time.time() - start_time) * 1000)

            self.state.metrics["duration_ms"] = duration
            self.state.status = "completed"
            self.state.completed_at = datetime.now()

            logger.info("✅ Done in %dms", duration)

            return self.state.to_dict()

        except Exception as e:
            logger.error("❌ Pipeline error: %s", e, exc_info=True)

            if self.state:
                self.state.status = "failed"
                self.state.errors.append(str(e))

            return {
                "status": "failed",
                "error": str(e),
            }

    # ================= AGENTS =================

    async def _planner(self, task: str) -> dict[str, Any]:
        """Planning agent - uses centralized prompts if available."""
        base_prompt = PLANNER_PROMPT or """You are a senior planner.
Return JSON:
{
  "goal": "...",
  "steps": ["...", "..."]
}

Task:
{task}
"""
        prompt = base_prompt.replace("{task}", task)
        return await self._llm_call(prompt, mode="fast")

    async def _architect(self, task: str, plan: dict[str, Any]) -> dict[str, Any]:
        """Architecture agent - uses centralized prompts if available."""
        base_prompt = ARCHITECT_PROMPT or """You are a software architect.
Plan:
{plan}

Return JSON:
{{
  "files": [
    {{"name": "main.py", "role": "..."}}
  ]
}}
"""
        prompt = base_prompt.replace("{plan}", str(plan))
        return await self._llm_call(prompt, mode="reasoning")

    async def _coder(self, task: str, architecture: dict[str, Any]) -> dict[str, Any]:
        """Code generation agent - uses centralized prompts if available."""
        base_prompt = CODER_PROMPT or """You are a senior Python engineer.
Architecture:
{architecture}

Return JSON:
{{
  "files": {{
    "main.py": "code here"
  }}
}}
"""
        prompt = base_prompt.replace("{architecture}", str(architecture))
        return await self._llm_call(prompt, mode="code")

    async def _reviewer(self, code: dict[str, Any]) -> dict[str, Any]:
        """Code review agent - uses centralized prompts if available."""
        base_prompt = REVIEWER_PROMPT or """Review this code and detect issues.
Code:
{code}

Return JSON:
{{
  "issues": ["..."],
  "fixes": ["..."]
}}
"""
        prompt = base_prompt.replace("{code}", str(code))
        return await self._llm_call(prompt, mode="fast")

    async def _runner(self, code: dict[str, Any]) -> dict[str, Any]:
        """
        Execute code in sandbox with auto-fix loop.

        Flow:
          1. Execute code
          2. If failure → Generate fix prompt
          3. Call LLM for correction
          4. Re-execute
          5. Max retry = 3
        """
        logger.info("🔨 Starting code execution + auto-fix loop")

        max_retry = 3
        attempt = 0
        files = code.get("files", {})
        execution: dict[str, Any] = {"success": False, "stdout": "", "stderr": "No execution attempted"}

        while attempt < max_retry:
            attempt += 1
            logger.info("[Auto-Fix] Attempt %d/%d", attempt, max_retry)

            # Execute sandboxed
            execution = await asyncio.to_thread(
                self.executor.run,
                files,
            )

            self.state.tests = execution

            # Check success
            if execution.get("success"):
                logger.info("✅ Execution success (attempt %d)", attempt)
                return execution

            # Failure → Auto-fix
            logger.warning("❌ Execution failed (attempt %d)", attempt)
            logger.warning("🔧 Auto-fix triggered")

            try:
                # Generate fix prompt
                error = execution.get("stderr", "") or execution.get("stdout", "")
                main_file = next(iter(files.keys()), "main.py")
                current_code = files.get(main_file, "")

                base_fix = FIX_PROMPT or """Fix this Python code.
Error:
{error}

Current code:
{current_code}

Return ONLY JSON:
{{
  "files": {{
    "{main_file}": "fixed code here"
  }}
}}

Retry count: {attempt}
Max retries: {max_retry}
"""
                fix_prompt = base_fix.format(
                    error=error,
                    current_code=current_code,
                    main_file=main_file,
                    attempt=attempt,
                    max_retry=max_retry,
                )

                # Fix code
                fixed = await self._llm_call(fix_prompt, mode="code")
                new_files = fixed.get("files")

                # Handle different response formats
                if isinstance(new_files, dict):
                    files.update(new_files)
                    logger.info("🔧 Applied fix for %s", main_file)
                elif isinstance(fixed, dict):
                    # Try to extract files from response
                    if "files" in fixed:
                        files.update(fixed["files"])
                    elif "main.py" in fixed:
                        files = {"main.py": fixed["main.py"]}
                    else:
                        logger.warning("⚠️ Invalid fix format, keeping previous files")
                else:
                    logger.warning("⚠️ Invalid fix response, keeping previous files")

            except Exception as fix_error:
                logger.error("❌ Auto-fix failed: %s", fix_error, exc_info=True)
                break

        # Failure after max_retry
        logger.error("❌ Exhausted max retry attempts (%d)", max_retry)
        if self.state:
            self.state.errors.append(f"Auto-fix failed after {max_retry} attempts")

        return execution

    async def _memory(self, task: str) -> list[dict[str, Any]]:
        """
        Memory search using FAISS adapter.

        Searches for relevant context in the vector store.
        Returns list of relevant documents with scores.
        """
        try:
            from core.memory import get_memory_manager

            # Use singleton to avoid reloading model
            memory = get_memory_manager()
            results = memory.search(task, k=3)
            return results  # Already returns [{"text": ..., "score": ...}]
        except Exception as e:
            logger.warning("⚠️ FAISS memory search failed: %s", e)
            return []

    # ================= CORE =================

    async def _llm_call(
        self,
        prompt: str,
        mode: str,
    ) -> dict[str, Any]:
        """
        Call LLM via router + safe JSON parsing.
        """
        loop = asyncio.get_running_loop()

        response = await loop.run_in_executor(
            None,
            lambda: self.router.generate(prompt, mode),
        )

        return self._safe_json(response)

    def _safe_json(self, text: str) -> dict[str, Any]:
        """
        Safely parse JSON from LLM response.
        Logs warning when falling back to raw response.
        """
        try:
            return json.loads(text)
        except Exception:
            # Try to extract JSON from markdown blocks
            cleaned = text.strip()
            if cleaned.startswith("```"):
                # Handle markdown code blocks
                lines = cleaned.split("\n")
                json_lines = [
                    line for line in lines
                    if not line.startswith("```") and not line.startswith("json")
                ]
                cleaned = "\n".join(json_lines)
                try:
                    return json.loads(cleaned)
                except Exception:
                    pass

            # Log warning for invalid JSON
            logger.warning(
                "⚠️ LLM returned invalid JSON (%s chars), falling back to raw. "
                "Response: %s",
                len(text),
                text[:200],
            )

            return {
                "raw": text[:500],  # Truncate raw response
                "error": "invalid_json",
            }