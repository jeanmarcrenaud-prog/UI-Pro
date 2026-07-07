"""
Code Review Module - Static analysis before executing LLM-generated code.
Supports: Bandit (security) and Pylint (style & bugs).
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


# Weighted scoring: security (3x) > performance (2x) > readability (1x)
SEVERITY_WEIGHTS = {
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
}
MAX_SCORE_PER_ISSUE = 5  # Max penalty points per issue
logger = logging.getLogger(__name__)

@dataclass
class ReviewResult:
    """Result of a code review scan."""
    success: bool
    issues: list[dict[str, Any]]
    tool: str
    summary: str
    raw_output: str = ""
    weighted_score: float = 0.0  # 0-100, higher is better

    success: bool
    issues: list[dict[str, Any]]
    tool: str
    summary: str
    raw_output: str = ""
    weighted_score: float = 0.0  # 0-100, higher is better


class CodeReviewer:
    """Runs security and quality checks on Python code before execution."""

    def __init__(
        self,
        tools: list[str] | None = None,
        fail_on: list[str] | None = None,
        bandit_config: Path | None = None,
    ):
        self.tools = tools or ["bandit"]
        self.fail_on = {level.lower() for level in (fail_on or ["high", "medium"])}
        self.bandit_config = bandit_config

    def review(self, code: str) -> ReviewResult:
        """Review code using configured tools."""
        if not code or not code.strip():
            return ReviewResult(success=True, issues=[], tool="", summary="Empty code")

        all_issues: list[dict[str, Any]] = []

        with NamedTemporaryFile(
            mode="w", suffix=".py", delete=True, encoding="utf-8"
        ) as tmp:
            tmp.write(code)
            tmp.flush()
            filepath = tmp.name

            for tool in self.tools:
                if tool == "bandit":
                    issues = self._run_bandit(filepath)
                    all_issues.extend(issues)
                elif tool == "pylint":
                    issues = self._run_pylint(filepath)
                    all_issues.extend(issues)

        # Determine if we should fail
        has_critical_issues = any(
            issue.get("severity", "").lower() in self.fail_on for issue in all_issues
        )

        # Calculate weighted score
        weighted = self.calculate_weighted_score(all_issues)

        return ReviewResult(
            success=not has_critical_issues,
            issues=all_issues,
            tool=", ".join(self.tools),
            summary=f"Found {len(all_issues)} issue(s) | Score: {weighted:.0f}/100",
            raw_output="",
            weighted_score=weighted,
        )

    def _run_bandit(self, filepath: str) -> list[dict[str, Any]]:
        """Run Bandit security linter."""
        issues: list[dict[str, Any]] = []
        cmd = ["bandit", "-f", "json", "-r", filepath]

        if self.bandit_config and self.bandit_config.exists():
            cmd.extend(["--configfile", str(self.bandit_config)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=25,
            )

            if result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    for finding in data.get("results", []):
                        issues.append(
                            {
                                "tool": "bandit",
                                "severity": finding.get(
                                    "issue_severity", "medium"
                                ).lower(),
                                "message": finding.get("issue_text", ""),
                                "line": finding.get("line_number"),
                                "code": finding.get("code"),
                                "test_id": finding.get("test_id"),
                            }
                        )
                except json.JSONDecodeError:
                    logger.warning("Failed to parse bandit JSON output")

            # If bandit failed for other reasons
            if result.returncode not in (0, 1):  # 1 = issues found
                logger.warning(
                    f"Bandit exited with code {result.returncode}: {result.stderr}"
                )

        except FileNotFoundError:
            logger.warning("bandit not installed. Skipping security scan.")
        except subprocess.TimeoutExpired:
            logger.warning("Bandit timed out")
        except Exception as e:
            logger.error(f"Unexpected error running bandit: {e}")

        return issues

    def _run_pylint(self, filepath: str) -> list[dict[str, Any]]:
        """Run Pylint for code quality."""
        issues: list[dict[str, Any]] = []
        try:
            result = subprocess.run(
                ["pylint", "--output-format=json", filepath],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    for msg in data:
                        severity = "low"
                        msg_type = msg.get("type", "")
                        if msg_type == "error":
                            severity = "high"
                        elif msg_type in ("warning", "refactor"):
                            severity = "medium"

                        issues.append(
                            {
                                "tool": "pylint",
                                "severity": severity,
                                "message": msg.get("message", ""),
                                "line": msg.get("line"),
                                "column": msg.get("column"),
                                "symbol": msg.get("symbol"),
                            }
                        )
                except json.JSONDecodeError:
                    logger.warning("Failed to parse pylint JSON output")

        except FileNotFoundError:
            logger.warning("pylint not installed. Skipping linting.")
        except subprocess.TimeoutExpired:
            logger.warning("Pylint timed out")
        except Exception as e:
            logger.error(f"Unexpected error running pylint: {e}")

        return issues
    def calculate_weighted_score(self, issues: list[dict[str, Any]]) -> float:
        """Calculate weighted score 0-100. Higher is better.

        Security issues (HIGH severity from Bandit) = 3x weight
        Performance issues (MEDIUM) = 2x weight
        Readability issues (LOW) = 1x weight
        """
        if not issues:
            return 100.0

        total_penalty = 0.0
        max_possible_penalty = 0.0

        for issue in issues:
            severity = issue.get("severity", "low").lower()
            weight = SEVERITY_WEIGHTS.get(severity, 1.0)
            penalty = weight * MAX_SCORE_PER_ISSUE
            total_penalty += penalty
            max_possible_penalty += penalty * 5  # Assume up to 5 issues per severity level

        if max_possible_penalty == 0:
            return 100.0

        score = max(0.0, 100.0 - (total_penalty / max_possible_penalty * 100))
        return round(score, 1)


# ====================== Singleton ======================

_reviewer: CodeReviewer | None = None


def get_reviewer(
    tools: list[str] | None = None,
    fail_on: list[str] | None = None,
    bandit_config: Path | None = None,
) -> CodeReviewer:
    """Get or create the singleton CodeReviewer."""
    global _reviewer
    if _reviewer is None:
        _reviewer = CodeReviewer(
            tools=tools, fail_on=fail_on, bandit_config=bandit_config
        )
    return _reviewer


def review_code(code: str) -> ReviewResult:
    """Convenience function to review code before execution."""
    return get_reviewer().review(code)
