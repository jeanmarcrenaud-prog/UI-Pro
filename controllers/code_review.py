"""
Code Review Module - Run bandit/pylint before code execution.
"""

import subprocess
import tempfile
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Code review result"""
    success: bool
    issues: list
    tool: str
    output: str


class CodeReviewer:
    """Run static analysis tools on code before execution"""
    
    def __init__(
        self,
        tools: list = None,
        fail_on: list = None
    ):
        """
        Initialize code reviewer.
        
        Args:
            tools: List of tools to run (bandit, pylint)
            fail_on: Severity levels to fail on (high, medium, low)
        """
        self.tools = tools or ["bandit"]
        self.fail_on = fail_on or ["high", "medium"]
    
    def review(self, code: str) -> ReviewResult:
        """
        Run code review on provided code.
        
        Args:
            code: Python code to review
            
        Returns:
            ReviewResult with success status and issues
        """
        all_issues = []
        
        # Write code to temp file for analysis
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write(code)
            temp_path = f.name
        
        try:
            # Run each tool
            for tool in self.tools:
                if tool == "bandit":
                    result = self._run_bandit(temp_path)
                    all_issues.extend(result.get("issues", []))
                elif tool == "pylint":
                    result = self._run_pylint(temp_path)
                    all_issues.extend(result.get("issues", []))
            
            # Check if any issues should fail the build
            has_failures = any(
                issue.get("severity", "").lower() in self.fail_on
                for issue in all_issues
            )
            
            return ReviewResult(
                success=not has_failures,
                issues=all_issues,
                tool=", ".join(self.tools),
                output=f"Found {len(all_issues)} issues"
            )
            
        finally:
            # Cleanup temp file
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass
    
    def _run_bandit(self, filepath: str) -> dict:
        """Run bandit static analysis"""
        try:
            result = subprocess.run(
                ["bandit", "-f", "json", filepath],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            issues = []
            
            # Parse bandit JSON output
            if result.stdout:
                import json
                try:
                    data = json.loads(result.stdout)
                    for finding in data.get("results", []):
                        issues.append({
                            "tool": "bandit",
                            "severity": finding.get("issue_severity", "medium"),
                            "message": finding.get("issue_text", ""),
                            "line": finding.get("line_number", 0),
                        })
                except json.JSONDecodeError:
                    pass
            
            return {"issues": issues}
            
        except FileNotFoundError:
            logger.warning("bandit not installed - skipping")
            return {"issues": []}
        except Exception as e:
            logger.warning(f"Bandit error: {e}")
            return {"issues": []}
    
    def _run_pylint(self, filepath: str) -> dict:
        """Run pylint static analysis"""
        try:
            result = subprocess.run(
                ["pylint", "--output-format=json", filepath],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            issues = []
            
            # Parse pylint JSON output
            if result.stdout:
                import json
                try:
                    data = json.loads(result.stdout)
                    for msg in data:
                        severity = "low"
                        if msg.get("type") == "error":
                            severity = "high"
                        elif msg.get("type") == "warning":
                            severity = "medium"
                        
                        issues.append({
                            "tool": "pylint",
                            "severity": severity,
                            "message": msg.get("message", ""),
                            "line": msg.get("line", 0),
                        })
                except json.JSONDecodeError:
                    pass
            
            return {"issues": issues}
            
        except FileNotFoundError:
            logger.warning("pylint not installed - skipping")
            return {"issues": []}
        except Exception as e:
            logger.warning(f"Pylint error: {e}")
            return {"issues": []}


# Singleton instance
_reviewer: Optional[CodeReviewer] = None


def get_reviewer(
    tools: list = None,
    fail_on: list = None
) -> CodeReviewer:
    """Get singleton code reviewer"""
    global _reviewer
    if _reviewer is None:
        _reviewer = CodeReviewer(tools=tools, fail_on=fail_on)
    return _reviewer


def review_code(code: str) -> ReviewResult:
    """Convenience function to review code"""
    return get_reviewer().review(code)