"""
Sandbox sécurisé pour exécution de code Python généré par LLM.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import multiprocessing
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.domain.core.code_review import ReviewResult, review_code

logger = logging.getLogger(__name__)


SAFE_BUILTINS = {
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "print": print,
    "str": str,
    "int": int,
    "float": float,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
}


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    output: str = ""
    error: str = ""
    execution_time_ms: float = 0.0
    review_result: Optional[ReviewResult] = None


class CodeExecutionService:
    TIMEOUT_SECONDS = 5

    BLOCKED_PATTERNS = {
        "os.system",
        "subprocess",
        "socket",
        "open(",
        "eval(",
        "exec(",
        "__import__",
        "shutil",
        "pathlib",
        "sys.exit",
    }

    async def execute(
        self,
        code: str,
        globals_dict: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:

        if not code.strip():
            return ExecutionResult(False, error="empty code")

        lowered = code.replace(" ", "")

        for pattern in self.BLOCKED_PATTERNS:
            if pattern.replace(" ", "") in lowered:
                return ExecutionResult(
                    False,
                    error=f"blocked dangerous pattern: {pattern}",
                )

        review = review_code(code)

        if not review.success:
            return ExecutionResult(
                False,
                error="static review failed",
                review_result=review,
            )

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._run_sync,
                    code,
                    globals_dict or {},
                    review,
                ),
                timeout=self.TIMEOUT_SECONDS,
            )

        except asyncio.TimeoutError:
            return ExecutionResult(False, error="execution timeout")

        except Exception as exc:
            logger.exception("execution failed")
            return ExecutionResult(False, error=str(exc))

    def _run_sync(
        self,
        code: str,
        globals_dict: Dict[str, Any],
        review: ReviewResult,
    ) -> ExecutionResult:

        stdout = io.StringIO()

        safe_globals = {
            "__builtins__": SAFE_BUILTINS,
            **globals_dict,
        }

        try:
            with contextlib.redirect_stdout(stdout):
                exec(code, safe_globals, {})

            return ExecutionResult(
                success=True,
                output=stdout.getvalue(),
                review_result=review,
            )

        except Exception:
            return ExecutionResult(
                success=False,
                error=traceback.format_exc(limit=5),
                review_result=review,
            )