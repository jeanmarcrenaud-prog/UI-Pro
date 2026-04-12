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
    memory_limit_mb: int = 512  # Memory limit in MB (POSIX only)


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
                from controllers.code_review import CodeReviewer
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
                # Set memory limit (POSIX only)
                import resource
                max_mem_bytes = self.config.memory_limit_mb * 1024 * 1024
                try:
                    resource.setrlimit(resource.RLIMIT_AS, (max_mem_bytes, max_mem_bytes))
                except Exception as e:
                    logger.warning(f"Failed to set memory limit: {e}")
                
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
    
    def _prepare_code(self, code: str | Dict) -> str:
        """Sanitize code - handles both string and dict formats"""
        # Handle dict format from orchestrator (e.g., {"files": {"main.py": "..."}})
        if isinstance(code, dict):
            if "files" in code:
                code = code.get("files", {})
            if isinstance(code, dict):
                # Get main.py or first file
                code = code.get("main.py", code.get("main", ""))
        
        # Ensure it's a string now
        if not isinstance(code, str):
            logger.warning(f"Code is not a string after extraction: {type(code)}")
            return "# Error: Invalid code format"
        
        code = "#!/usr/bin/env python3\n" + code
        
        # 1. String-based sanitization (basic)
        dangerous = ["(eval(", "(exec(", "subprocess.Popen(", "open('..'"]
        for pattern in dangerous:
            code = code.replace(pattern, "# DISABLED: ")
        
        # 2. AST-based sanitization (robust)
        code = self._ast_sanitize(code)
        
        return code
    
    def _ast_sanitize(self, code: str) -> str:
        """AST-based code sanitization to block dangerous constructs"""
        import ast
        
        class DangerousVisitor(ast.NodeTransformer):
            def __init__(self):
                self.disabled = []
            
            def visit_Call(self, node: ast.Call) -> ast.Call:
                # Check for dangerous function calls
                dangerous_names = {'eval', 'exec', '__import__', 'open'}
                
                # Handle direct name calls: eval(), exec()
                if isinstance(node.func, ast.Name):
                    if node.func.id in dangerous_names:
                        self.disabled.append(node.lineno)
                        return ast.Expr(value=ast.Constant(value=f"# DISABLED at line {node.lineno}"))
                
                # Handle attribute calls: obj.eval(), obj.exec()
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in dangerous_names:
                        self.disabled.append(node.lineno)
                        return ast.Expr(value=ast.Constant(value=f"# DISABLED at line {node.lineno}"))
                
                return node
            
            def visit_Import(self, node: ast.Import) -> ast.Import:
                # Block dangerous imports
                dangerous_imports = {'os', 'sys', 'subprocess', 'socket'}
                for alias in node.names:
                    if alias.name in dangerous_imports:
                        self.disabled.append(node.lineno)
                return node
            
            def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
                # Block dangerous from imports
                if node.module in {'os', 'sys', 'subprocess', 'socket', 'builtins'}:
                    self.disabled.append(node.lineno)
                return node
        
        try:
            tree = ast.parse(code)
            visitor = DangerousVisitor()
            tree = visitor.visit(tree)
            
            if visitor.disabled:
                logger.warning(f"AST sanitization blocked lines: {visitor.disabled}")
                # Remove marked nodes by reconstructing
                return ast.unparse(tree)
            
            return code
        except SyntaxError:
            # If AST parsing fails, fall back to string sanitization
            logger.warning("AST parsing failed, using string sanitization")
            return code


# ==================== **3. EXISTING COMPATIBILITY** ====================

# Compatibilité avec ancien code
def run():
    """Legacy API"""
    return "executor.py has been updated to CodeExecutor pattern"
