# services/code_execution.py - Secure Execution of LLM-Generated Code
"""
Service for safely executing LLM-generated Python code with static analysis.
"""

import logging
import traceback
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

from backend.domain.core.code_review import review_code, ReviewResult

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of code execution after review and safety checks."""
    success: bool
    output: str = ""
    error: str = ""
    review_result: Optional[ReviewResult] = None
    execution_time_ms: float = 0.0


class CodeExecutionService:
    """
    Secure code execution with mandatory static analysis.
    Designed to safely run LLM-generated Python code.
    """

    def __init__(self, enable_review: bool = True, fail_on_review: bool = True):
        self.enable_review = enable_review
        self.fail_on_review = fail_on_review

    def execute(self, code: str, globals_dict: Optional[Dict] = None) -> ExecutionResult:
        """Review then execute code safely (single-file)."""
        start_time = time.time()

        if not code or not code.strip():
            return ExecutionResult(success=False, error="Empty code provided")

        # Security: block dangerous patterns
        dangerous = [
            "os.system", "os.popen", "subprocess", "open(",
            "().__", "__import__", "eval(", "exec(",
            "sys.", "os.environ", " pathlib",
            ".read()", ".write()", "shutil", "socket.",
        ]
        code_flat = code.replace(" ", "").replace("\n", "")
        for pattern in dangerous:
            if pattern.replace(" ", "") in code_flat:
                return ExecutionResult(
                    success=False,
                    error=f"Blocked dangerous pattern: {pattern.strip()}"
                )

        review_result: Optional[ReviewResult] = None

        # === 1. STATIC CODE REVIEW ===
        if self.enable_review:
            logger.info("Performing static analysis before execution...")
            review_result = review_code(code)

            if not review_result.success and self.fail_on_review:
                issues = "\n".join(
                    f"• {issue.get('tool', 'unknown')} | {issue.get('severity', 'unknown')} | {issue.get('message', '')}"
                    for issue in review_result.issues[:8]
                )
                return ExecutionResult(
                    success=False,
                    error=f"Code review failed:\n{issues}",
                    review_result=review_result
                )

            if review_result.issues:
                logger.warning(f"Code review found {len(review_result.issues)} issues")

        # === 2. SAFE EXECUTION ===
        try:
            local_dict: Dict[str, Any] = {}
            global_dict = globals_dict or {}

            # Very restricted globals
            safe_globals = {
                "__builtins__": {
                    "print": print,
                    "range": range,
                    "len": len,
                    "str": str,
                    "int": int,
                    "float": float,
                    "list": list,
                    "dict": dict,
                    "sum": sum,
                    "min": min,
                    "max": max,
                },
                **global_dict
            }

            exec(code, safe_globals, local_dict)

            output = local_dict.get("result") or str(local_dict)

            return ExecutionResult(
                success=True,
                output=str(output),
                review_result=review_result,
                execution_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error(f"Code execution failed: {error_msg}\n{traceback.format_exc()}")

            return ExecutionResult(
                success=False,
                error=error_msg,
                review_result=review_result,
                execution_time_ms=(time.time() - start_time) * 1000
            )

    def run(self, files: Dict[str, Any]) -> ExecutionResult:
        """Execute multiple files from a {"files": {"name.py": "content"}} dict."""
        if not isinstance(files, dict):
            return ExecutionResult(success=False, error=f"Expected dict, got {type(files).__name__}")

        file_dict = files.get("files", files)  # Support both {"files": {...}} and flat dict

        if not file_dict or not isinstance(file_dict, dict):
            return ExecutionResult(success=False, error="No files to execute")

        # Path traversal defense
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-/")
        for fname in file_dict:
            if not all(c in safe_chars for c in fname) or ".." in fname or fname.startswith("/"):
                return ExecutionResult(success=False, error=f"Invalid filename (path traversal): {fname}")

        results: list[Dict[str, Any]] = []
        all_success = True

        for filename, code in file_dict.items():
            if not isinstance(code, str):
                logger.warning(f"Skipping {filename}: not a string")
                continue
            logger.info(f"Executing file: {filename}")
            result = self.execute(code)
            results.append({
                "filename": filename,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
            })
            if not result.success:
                all_success = False
            # Stop on first failure
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


# ====================== Singleton ======================

_execution_service: Optional[CodeExecutionService] = None


def get_code_execution_service(
    enable_review: bool = True,
    fail_on_review: bool = True
) -> CodeExecutionService:
    """Get singleton CodeExecutionService."""
    global _execution_service
    if _execution_service is None:
        _execution_service = CodeExecutionService(
            enable_review=enable_review,
            fail_on_review=fail_on_review
        )
    return _execution_service


def execute_code(
    code: str,
    globals_dict: Optional[Dict] = None
) -> ExecutionResult:
    """Convenience function to execute code safely."""
    return get_code_execution_service().execute(code, globals_dict)