# core/executor.py - Code Executor (Multi-lang + Sandbox + Code Review)
#
# Role: Secure multi-language code execution with optional code review
# Used by: Agent execution, code validation, code review
# - Pygments-based language detection
# - Language-specific execution (Python, JS, TS, Bash, HTML)
# - Temporary directory isolation with timeout per language
# - Optional code review integration

import logging
from dataclasses import dataclass
from typing import Any

from backend.infrastructure.multi_lang_executor import MultiLangExecutor

logger = logging.getLogger(__name__)


# ==================== **1. CONFIG** ====================


@dataclass
class ExecutionConfig:
    """Configuration for code execution"""

    code_review_enabled: bool = False


# ==================== **2. CODE EXECUTOR CLASS** ====================


class CodeExecutor:
    """
    Multi-language executor with optional code review.

    Architecture:
      - Uses MultiLangExecutor for language detection + sandbox execution
      - Integrates optional code-review pre-execution check
      - Supports Python, JavaScript, TypeScript, Bash, HTML
      - Language auto-detection via Pygments
    """

    def __init__(self, code_review_enabled: bool = False):
        self.config = ExecutionConfig(code_review_enabled=code_review_enabled)
        self._executor = MultiLangExecutor()
        self._reviewer = None

        if self.config.code_review_enabled:
            try:
                from backend.domain.core.code_review import CodeReviewer

                self._reviewer = CodeReviewer()
            except ImportError:
                logger.warning("Code review not available")

    def run(
        self, code: str, filename: str | None = None, timeout: int | None = None
    ) -> dict[str, Any]:
        """
        Execute code in sandbox with optional code review.

        Args:
            code: Source code to execute
            filename: Optional filename for language detection
            timeout: Optional execution timeout (uses language default if None)

        Returns:
            Dict with keys: success, language, output, error, execution_time, code_hash, review
        """
        review_result = None

        # Run code review first if enabled
        if self.config.code_review_enabled and self._reviewer:
            try:
                review_result = self._reviewer.review(code)
                if not review_result.success:
                    logger.warning(f"Code review found issues: {review_result.issues}")
            except Exception as e:
                logger.warning(f"Code review failed: {e}")

        # Execute code via MultiLangExecutor
        result = self._executor.execute(code, filename=filename, timeout=timeout)

        # Add stdout/stderr aliases for backwards compatibility
        if "output" in result and "stdout" not in result:
            result["stdout"] = result["output"]
        if result.get("error"):
            result.setdefault("stderr", result["error"])

        # Attach review results if available
        if review_result:
            result["review"] = {
                "enabled": True,
                "issues": review_result.issues,
                "passed": review_result.success,
            }
        else:
            result["review"] = {
                "enabled": self.config.code_review_enabled,
                "issues": [],
                "passed": True,
            }

        return result


# ==================== **3. BACKWARD COMPATIBILITY** ====================


def run():
    """Legacy API"""
    return "executor.py has been updated to multi-language CodeExecutor"
