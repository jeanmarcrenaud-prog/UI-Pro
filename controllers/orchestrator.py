# 🚀 Async Orchestrator - PRO VERSION + Auto-Fix
# ⚠️ DEPRECATED: Use orchestrator_async.py instead (core/orchestrator_async.py)
# This file is legacy and may conflict with new architecture

from typing import Dict, Any
from datetime import datetime
import asyncio
import time
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.state import StateManager
from controllers.executor import CodeExecutor  # Use CodeExecutor
from core.prompts import PLANNER_PROMPT, ARCHITECT_PROMPT, CODER_PROMPT, REVIEWER_PROMPT, FIX_PROMPT

# Import agents from llm package
try:
    from llm import planner, architect, coder, reviewer
except ImportError as e:
    logger.warning(f"Agents not available from llm package: {e}")
    # Will use _planner() instead


class Orchestrator:
    def __init__(self):
        self.state_manager = StateManager()
        self.router = LLMRouter()
        self.state = None

    async def run(self, task: str) -> Dict[str, Any]:
        start_time = time.time()

        try:
            # ================= STATE =================
            self.state = self.state_manager.create(task_id=task[:8])
            self.state.task = task
            self.state.status = "running"

            logger.info(f"🚀 Starting pipeline: {task}")

            # ================= STEP 1: PARALLEL =================
            logger.info("Step 1: Planning + Memory")

            plan, memory = await asyncio.gather(
                self._planner(task),
                self._memory(task)
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

            logger.info(f"✅ Done in {duration}ms")

            return self.state.to_dict()

        except Exception as e:
            logger.error(f"❌ Pipeline error: {e}", exc_info=True)

            if self.state:
                self.state.status = "failed"
                self.state.errors.append(str(e))

            return {
                "status": "failed",
                "error": str(e),
            }

    # ================= AGENTS =================

    async def _planner(self, task: str) -> Dict:
        prompt = f"""
You are a senior planner.

Return JSON:
{{
  "goal": "...",
  "steps": ["...", "..."]
}}

Task:
{task}
"""

        return await self._llm_call(prompt, "fast")

    async def _architect(self, task: str, plan: Dict) -> Dict:
        prompt = f"""
You are a software architect.

Plan:
{plan}

Return JSON:
{{
  "files": [
    {{"name": "main.py", "role": "..."}}
  ]
}}
"""

        return await self._llm_call(prompt, "reasoning")

    async def _coder(self, task: str, architecture: Dict) -> Dict:
        prompt = f"""
You are a senior Python engineer.

Architecture:
{architecture}

Return JSON:
{{
  "files": {{
    "main.py": "code here"
  }}
}}
"""

        return await self._llm_call(prompt, "code")

    async def _reviewer(self, code: Dict) -> Dict:
        prompt = f"""
Review this code and detect issues.

Code:
{code}

Return JSON:
{{
  "issues": ["..."],
  "fixes": ["..."]
}}
"""
        return await self._llm_call(prompt, "fast")

    async def _runner(self, code: Dict) -> Dict:
        """
        Exécuter code avec sandbox.
        
        Auto-fix loop:
          1. Exécuter code
          2. Si échec → Générer fix prompt
          3. Appeller LLM pour corrigé
          4. Re-exécuter
          5. Max retry = 3
        """
        logger.info("🔨 Starting code execution + auto-fix loop")
        
        max_retry = 3
        attempt = 0
        
        while attempt < max_retry:
            attempt += 1
            logger.info(f"[Auto-Fix] Attempt {attempt}/{max_retry}")
            
            # Execution sandboxed
            execution = await asyncio.to_thread(
                executor.run,
                code.get("files", {})
            )
            
            self.state.tests = execution
            
            # Vérifie succès
            if execution.get("success"):
                logger.info(f"✅ Execution success (attempt {attempt})")
                return execution
            
            # Échec → Auto-fix
            logger.warning(f"❌ Execution failed (attempt {attempt})")
            logger.warning("🔧 Auto-fix triggered")
            
            try:
                # Générer fix prompt
                error = execution.get("stderr", "")
                code_content = code.get("files", {}).get("main.py", "")
                
                fix_prompt = f"""Fix this Python code.

Error:
{error}

Current code:
{code_content}

Return ONLY JSON:
{{
  "files": {{
    "main.py": "fixed code here"
  }}
}}

Retry count: {attempt}
Max retries: {max_retry}
"""
                
                # Corriger code
                fixed_code = await self._llm_call(fix_prompt, "code")
                logger.info(f"🔧 Applied fix (length=%d)", len(fixed_code.get("raw", "")) if isinstance(fixed_code, dict) else len(str(fixed_code)))
                
                # Normalize code format - handle both dict and string fixes
                if isinstance(fixed_code, dict):
                    # If already a dict structure, pass through as-is
                    # executor._prepare_code will normalize it
                    code = fixed_code
                else:
                    # Wrap string fix in files structure
                    code = {"files": {"main.py": fixed_code}}
                
                # Continue loop
                continue
                
            except Exception as fix_error:
                logger.error(f"❌ Auto-fix failed: {fix_error}", exc_info=True)
                break
        
        # Échec après max_retry
        logger.error(f"❌ Exhausted max retry attempts ({max_retry})")
        if self.state:
            self.state.errors.append(f"Auto-fix failed after {max_retry} attempts")
        
        return execution

    async def _memory(self, task: str):
        """Retrieve memory context using FAISS"""
        # Import FAISS memory lazily to avoid import overhead
        try:
            from models.memory import MemoryManager
            
            # Get or create singleton memory manager
            if not hasattr(self, '_memory_manager'):
                self._memory_manager = MemoryManager()
            
            # Search for relevant context
            results = self._memory_manager.search(task, k=3)
            
            if results:
                logger.info(f"Found {len(results)} memory results for task: {task[:50]}...")
                return results
            
            logger.debug(f"No memory results found for task: {task[:50]}...")
            return []
            
        except ImportError as e:
            logger.warning(f"Memory module not available: {e}")
            return []
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    # ================= CORE =================

    async def _llm_call(self, prompt: str, mode: str) -> Dict:
        """
        Call LLM via router + safe JSON
        """

        loop = asyncio.get_event_loop()

        response = await loop.run_in_executor(
            None,
            lambda: self.router.generate(prompt, mode)
        )

        return self._safe_json(response)

    def _safe_json(self, text: str) -> Dict:
        import json

        try:
            return json.loads(text)
        except Exception:
            return {
                "raw": text,
                "error": "invalid_json"
            }