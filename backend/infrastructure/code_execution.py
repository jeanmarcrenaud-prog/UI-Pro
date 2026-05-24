"""
Sandbox sécurisé pour exécution de code Python généré par LLM.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import traceback
from dataclasses import dataclass
from typing import Any

from backend.domain.core.code_review import ReviewResult, review_code
from backend.infrastructure.multi_lang_executor import MultiLangExecutor
from backend.infrastructure.secure_executor import SecureCodeExecutor

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
    review_result: ReviewResult | None = None
    sandbox_type: str = "in-process"  # "in-process" or "docker"


class CodeExecutionService:
    TIMEOUT_SECONDS = 5

    def __init__(self, use_docker: bool = False):
        # Secure executor with AST analysis (Python only)
        self._secure_executor = SecureCodeExecutor(
            timeout=self.TIMEOUT_SECONDS, memory_limit_mb=512
        )
        # Multi-language executor (Python, JS, Bash)
        self._multi_executor = MultiLangExecutor()
        # Docker sandbox (optional)
        self._docker_sandbox = None
        self._use_docker = use_docker

        if use_docker:
            try:
                from backend.infrastructure.docker_sandbox import get_docker_sandbox

                self._docker_sandbox = get_docker_sandbox()
                logger.info("Docker sandbox enabled for code execution")
            except ImportError as e:
                logger.warning(f"Docker sandbox not available: {e}")

    async def execute(
        self,
        code: str,
        globals_dict: dict[str, Any] | None = None,
        use_docker: bool | None = None,
    ) -> ExecutionResult:

        if not code.strip():
            return ExecutionResult(False, error="empty code")

        # Use Docker if requested and available
        use_docker = use_docker if use_docker is not None else self._use_docker
        if use_docker and self._docker_sandbox:
            return await self._execute_docker(code)

        # Static analysis via AST (catches dangerous imports, exec/eval, open())
        ast_safe, ast_msg = self._secure_executor._check_dangerous_code(code)
        if not ast_safe:
            return ExecutionResult(
                False,
                error=f"Code rejected: {ast_msg}",
            )

        review = review_code(code)

        if not review.success:
            return ExecutionResult(
                False,
                error="static review failed",
                review_result=review,
            )

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._run_sync,
                    code,
                    globals_dict or {},
                    review,
                ),
                timeout=self.TIMEOUT_SECONDS,
            )
            result.sandbox_type = "in-process"
            return result

        except asyncio.TimeoutError:
            return ExecutionResult(False, error="execution timeout")

        except Exception as exc:
            logger.exception("execution failed")
            return ExecutionResult(False, error=str(exc))

    async def _execute_docker(self, code: str) -> ExecutionResult:
        """Execute code in Docker sandbox."""
        if not self._docker_sandbox:
            return ExecutionResult(False, error="Docker sandbox not initialized")

        try:
            result = await self._docker_sandbox.execute(code, "python")
            return ExecutionResult(
                success=result.success,
                output=result.output,
                error=result.error,
                execution_time_ms=result.execution_time_ms,
                sandbox_type="docker",
            )
        except Exception as e:
            logger.exception("Docker execution failed")
            return ExecutionResult(
                False, error=f"Docker sandbox error: {e!s}", sandbox_type="docker"
            )

    def _run_sync(
        self,
        code: str,
        globals_dict: dict[str, Any],
        review: ReviewResult,
    ) -> ExecutionResult:
        """
        Execute code in a restricted in-process sandbox.

        SECURITY NOTES:
        - Uses a restricted SAFE_BUILTINS dict (no __import__, open, eval, exec)
        - Empty locals dict prevents variable leakage
        - AST analysis already validated no dangerous patterns
        - For stronger isolation, use the Docker sandbox or SecureCodeExecutor subprocess
        """
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

    def run(self, files: dict[str, Any]) -> ExecutionResult:
        """Execute multiple files from a {"files": {"name.py": "content"}} dict."""
        if not isinstance(files, dict):
            return ExecutionResult(
                False, error=f"Expected dict, got {type(files).__name__}"
            )

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
            results.append(
                {
                    "filename": filename,
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "execution_time_ms": result.execution_time_ms,
                }
            )
            if not result.success:
                all_success = False
            if not result.success:
                break

        combined_output = "\n".join(
            f"=== {r['filename']} ===\n{r['output'] or r['error']}" for r in results
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
        filename: str | None = None,
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
            error=result.get("error") or "",
            execution_time_ms=result["execution_time"] * 1000,
        )
