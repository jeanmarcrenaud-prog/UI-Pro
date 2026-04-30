# services/code_execution.py
"""
Service for safely executing LLM-generated Python code with static analysis.
"""

import logging
import traceback
from typing import Dict, Any, Optional
from dataclasses import dataclass

from core.code_review import review_code, ReviewResult  # Your module

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of code execution after review"""
    success: bool
    output: str = ""
    error: str = ""
    review_result: Optional[ReviewResult] = None
    execution_time: float = 0.0


class CodeExecutionService:
    """
    Secure code execution service with mandatory code review.
    """

    def __init__(self, enable_review: bool = True, fail_on_review: bool = True):
        self.enable_review = enable_review
        self.fail_on_review = fail_on_review

    def execute(self, code: str, globals_dict: Optional[Dict] = None) -> ExecutionResult:
        """
        Review then execute Python code safely.
        
        Args:
            code: Python code to execute
            globals_dict: Global variables to pass to exec()
            
        Returns:
            ExecutionResult with success status and output/error
        """
        if not code or not code.strip():
            return ExecutionResult(success=False, error="Empty code provided")

        review_result: Optional[ReviewResult] = None

        # === 1. CODE REVIEW ===
        if self.enable_review:
            logger.info("Running static analysis before execution...")
            review_result = review_code(code)

            if not review_result.success and self.fail_on_review:
                issues_summary = "\n".join(
                    f"- {issue.get('tool')} | {issue.get('severity')} | {issue.get('message')}"
                    for issue in review_result.issues[:10]  # Limit output
                )
                return ExecutionResult(
                    success=False,
                    error=f"Code review failed:\n{issues_summary}",
                    review_result=review_result
                )

            if review_result.issues:
                logger.warning(f"Code review found {len(review_result.issues)} issues "
                             f"(severity filter: {self.fail_on_review})")

        # === 2. CODE EXECUTION ===
        try:
            # Prepare execution environment
            local_dict: Dict[str, Any] = {}
            global_dict = globals_dict or {}

            # Add safe built-ins if needed
            safe_globals = {
                "__builtins__": __builtins__,
                **global_dict
            }

            logger.info("Executing reviewed code...")
            
            # Execute the code
            exec(code, safe_globals, local_dict)

            output = local_dict.get("result", str(local_dict))

            return ExecutionResult(
                success=True,
                output=str(output),
                review_result=review_result
            )

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error(f"Code execution failed: {error_msg}")
            logger.debug(traceback.format_exc())

            return ExecutionResult(
                success=False,
                error=error_msg,
                review_result=review_result
            )

    def should_fail(self, review_result: ReviewResult) -> bool:
        """Check if review result should block execution"""
        return not review_result.success


# ====================== Singleton ======================
_execution_service: Optional[CodeExecutionService] = None


def get_code_execution_service(
    enable_review: bool = True,
    fail_on_review: bool = True
) -> CodeExecutionService:
    """Get singleton instance of CodeExecutionService"""
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
    """Convenience function to execute code with review"""
    return get_code_execution_service().execute(code, globals_dict)