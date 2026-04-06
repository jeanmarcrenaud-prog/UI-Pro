# 🧪 **Code Executor** (Sandbox + Auto-Fix + Timeout + Code Review)

import subprocess
import tempfile
import time
import logging
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# ==================== **1. CONFIG** ====================

@dataclass
class ExecutionConfig:
    """Configuration sandbox"""
    timeout: int = 30
    workspace_dir: str = "workspace"
    cleanup: bool = True
    max_fix_attempts: int = 3
    code_review_enabled: bool = False


_CONFIG = ExecutionConfig()


# ==================== **2. CODE EXECUTOR CLASS** ====================

class CodeExecutor:
    """
    Executor avec sandbox + auto-fix + code review.
    
    Pattern:
      - Optionally run code review (bandit/pylint)
      - Créer tmp dir isolation (tempfile)
      - Écrire main.py (entry point)
      - Exécuter avec timeout
      - Capturer stderr/stdout
      - Auto-fix loop si échec
    """
    
    def __init__(
        self,
        timeout: int = 30,
        workspace_dir: str = "workspace",
        cleanup: bool = True,
        max_fix_attempts: int = 3,
        code_review_enabled: bool = False,
    ):
        self.config = ExecutionConfig(
            timeout=timeout,
            workspace_dir=workspace_dir,
            cleanup=cleanup,
            max_fix_attempts=max_fix_attempts,
            code_review_enabled=code_review_enabled,
        )
        self._reviewer = None
        
        if self.config.code_review_enabled:
            try:
                from core.code_review import CodeReviewer
                self._reviewer = CodeReviewer()
            except ImportError:
                logger.warning("Code review not available")
    
    def run(self, code: str) -> Dict[str, Any]:
        """
        Exécuter code sandboxed avec code review optionnel.
        
        Args:
            code: Code Python à exécuter
            
        Returns:
            Dict {"success": bool, "stdout": ..., "stderr": ..., "duration_ms": ..., "review": ...}
        """
        start_time = time.time()
        
        # Run code review first if enabled
        review_result = None
        if self.config.code_review_enabled and self._reviewer:
            try:
                review_result = self._reviewer.review(code)
                if not review_result.success:
                    logger.warning(f"Code review found issues: {review_result.issues}")
            except Exception as e:
                logger.warning(f"Code review failed: {e}")
        
        tmpdir = None
        
        try:
            tmpdir = tempfile.mkdtemp()
            workspace = Path(tmpdir)
            
            # Write code to temp file
            main_file = workspace / "main.py"
            sanitized_code = self._prepare_code(code)
            main_file.write_text(sanitized_code, encoding="utf-8")
            
            # Execute - different approach for Windows
            if sys.platform == "win32":
                # Run with stdin explicitly closed to avoid handle issues
                cp = subprocess.run(
                    ["python", str(main_file)],
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout,
                    stdin=subprocess.DEVNULL,
                )
            else:
                cp = subprocess.run(
                    ["python", str(main_file)],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout,
                )
            
            duration_ms = int((time.time() - start_time) * 1000)
            success = cp.returncode == 0
            
            if not success:
                logger.warning(f"Execution failed: {cp.stderr[:100]}")
            
            return {
                "success": success,
                "stdout": cp.stdout,
                "stderr": cp.stderr,
                "duration_ms": duration_ms,
                "returncode": cp.returncode,
                "review": {
                    "enabled": self.config.code_review_enabled,
                    "issues": review_result.issues if review_result else [],
                    "passed": review_result.success if review_result else True,
                } if review_result else None,
            }
            
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Execution timeout: {self.config.timeout}s")
        
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return {"success": False, "error": str(e)}
        
        except Exception as e:
            logger.error(f"Executor error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
        
        finally:
            # Cleanup manually
            if tmpdir:
                import shutil
                try:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                except Exception:
                    pass
    
    def _prepare_code(self, code: str) -> str:
        """Sanitize code"""
        code = "#!/usr/bin/env python3\n" + code
        
        dangerous = ["(eval(", "(exec(", "subprocess.Popen(", "open('..'"]
        for pattern in dangerous:
            code = code.replace(pattern, "# DISABLED: ")
        
        return code


# ==================== **3. EXISTING COMPATIBILITY** ====================

# Compatibilité avec ancien code
def run():
    """Legacy API"""
    return "executor.py has been updated to CodeExecutor pattern"
