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
        """Review then execute code safely."""
        start_time = time.time()

        if not code or not code.strip():
            return ExecutionResult(success=False, error="Empty code provided")

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