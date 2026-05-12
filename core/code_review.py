# core/code_review.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.domain.core.code_review instead

from backend.domain.core.code_review import (
    ReviewResult,
    CodeReviewer,
    get_reviewer,
    review_code,
)

__all__ = [
    "ReviewResult",
    "CodeReviewer",
    "get_reviewer",
    "review_code",
]
    issues: List[Dict[str, Any]]
    tool: str
    summary: str
    raw_output: str = ""


class CodeReviewer:
    """Runs security and quality checks on Python code before execution."""

    def __init__(
        self,
        tools: List[str] | None = None,
        fail_on: List[str] | None = None,
        bandit_config: Optional[Path] = None,
    ):
        self.tools = tools or ["bandit"]
        self.fail_on = {level.lower() for level in (fail_on or ["high", "medium"])}
        self.bandit_config = bandit_config

    def review(self, code: str) -> ReviewResult:
        """Review code using configured tools."""
        if not code or not code.strip():
            return ReviewResult(success=True, issues=[], tool="", summary="Empty code")

        all_issues: List[Dict[str, Any]] = []

        with NamedTemporaryFile(mode="w", suffix=".py", delete=True, encoding="utf-8") as tmp:
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

        return ReviewResult(
            success=not has_critical_issues,
            issues=all_issues,
            tool=", ".join(self.tools),
            summary=f"Found {len(all_issues)} issue(s)",
            raw_output="",
        )

    def _run_bandit(self, filepath: str) -> List[Dict[str, Any]]:
        """Run Bandit security linter."""
        issues: List[Dict[str, Any]] = []
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
                        issues.append({
                            "tool": "bandit",
                            "severity": finding.get("issue_severity", "medium").lower(),
                            "message": finding.get("issue_text", ""),
                            "line": finding.get("line_number"),
                            "code": finding.get("code"),
                            "test_id": finding.get("test_id"),
                        })
                except json.JSONDecodeError:
                    logger.warning("Failed to parse bandit JSON output")

            # If bandit failed for other reasons
            if result.returncode not in (0, 1):  # 1 = issues found
                logger.warning(f"Bandit exited with code {result.returncode}: {result.stderr}")

        except FileNotFoundError:
            logger.warning("bandit not installed. Skipping security scan.")
        except subprocess.TimeoutExpired:
            logger.warning("Bandit timed out")
        except Exception as e:
            logger.error(f"Unexpected error running bandit: {e}")

        return issues

    def _run_pylint(self, filepath: str) -> List[Dict[str, Any]]:
        """Run Pylint for code quality."""
        issues: List[Dict[str, Any]] = []
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

                        issues.append({
                            "tool": "pylint",
                            "severity": severity,
                            "message": msg.get("message", ""),
                            "line": msg.get("line"),
                            "column": msg.get("column"),
                            "symbol": msg.get("symbol"),
                        })
                except json.JSONDecodeError:
                    logger.warning("Failed to parse pylint JSON output")

        except FileNotFoundError:
            logger.warning("pylint not installed. Skipping linting.")
        except subprocess.TimeoutExpired:
            logger.warning("Pylint timed out")
        except Exception as e:
            logger.error(f"Unexpected error running pylint: {e}")

        return issues


# ====================== Singleton ======================

_reviewer: Optional[CodeReviewer] = None


def get_reviewer(
    tools: List[str] | None = None,
    fail_on: List[str] | None = None,
    bandit_config: Optional[Path] = None,
) -> CodeReviewer:
    """Get or create the singleton CodeReviewer."""
    global _reviewer
    if _reviewer is None:
        _reviewer = CodeReviewer(tools=tools, fail_on=fail_on, bandit_config=bandit_config)
    return _reviewer


def review_code(code: str) -> ReviewResult:
    """Convenience function to review code before execution."""
    return get_reviewer().review(code)