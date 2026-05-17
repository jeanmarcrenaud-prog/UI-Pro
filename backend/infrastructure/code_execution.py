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
from backend.infrastructure.secure_executor import SecureCodeExecutor
from backend.infrastructure.multi_lang_executor import MultiLangExecutor

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

    def __init__(self):
        # Secure executor with AST analysis (Python only)
        self._secure_executor = SecureCodeExecutor(
            timeout=self.TIMEOUT_SECONDS,
            memory_limit_mb=512
        )
        # Multi-language executor (Python, JS, Bash)
        self._multi_executor = MultiLangExecutor()

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

    def run(self, files: Dict[str, Any]) -> ExecutionResult:
        """Execute multiple files from a {"files": {"name.py": "content"}} dict."""
        if not isinstance(files, dict):
            return ExecutionResult(False, error=f"Expected dict, got {type(files).__name__}")

        file_dict = files.get("files", files)

        if not file_dict or not isinstance(file_dict, dict):
            return ExecutionResult(False, error="No files to execute")

        results = []
        all_success = True

        for filename, code in file_dict.items():
            if not isinstance(code, str):
                logger.warning(f"Skipping {filename}: not a string")
                continue
            logger.info(f"Executing file: {filename}")
            result = asyncio.run(self.execute(code))
            results.append({
                "filename": filename,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
            })
            if not result.success:
                all_success = False
            if not result.success:
                break

        combined_output = "\n".join(
            f"=== {r['filename']} ===\n{r['output'] or r['error']}"
            for r in results
        )

        return ExecutionResult(
            success=all_success,
            output=combined_output,
            error="" if all_success else results[-1].get("error", "Execution failed"),
            execution_time_ms=sum(r["execution_time_ms"] for r in results),
        )

    async def execute_multi(
        self,
        code: str,
        filename: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Exécute du code multi-langage (Python, JavaScript, Bash).
        Détection automatique du langage.
        """
        import time
        start = time.perf_counter()
        
        result = self._multi_executor.execute(code, filename)
        
        return ExecutionResult(
            success=result["success"],
            output=result["output"],
            error=result.get("error"),
            execution_time_ms=result["execution_time"] * 1000,
        )