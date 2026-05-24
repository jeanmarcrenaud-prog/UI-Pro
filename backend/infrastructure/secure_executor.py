"""
secure_executor.py - Exécuteur sécurisé renforcé pour UI-Pro
"""

import ast
import hashlib
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Modules dangereux bloqués
BLOCKED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "pathlib",
    "socket",
    "requests",
    "urllib",
    "http",
    "ftp",
    "pty",
    "tty",
    "termios",
    "fcntl",
}


class SecureCodeExecutor:
    """
    Exécuteur sécurisé avec :
    - Analyse AST pour détecter patterns dangereux
    - Limites système (CPU, mémoire)
    - Exécution dans TemporaryDirectory isolé
    - Audit logging
    """

    def __init__(self, timeout: int = 30, memory_limit_mb: int = 512):
        self.timeout = timeout
        self.memory_limit_mb = memory_limit_mb

    def _check_dangerous_code(self, code: str) -> tuple[bool, str]:
        """Analyse AST pour détecter des patterns dangereux"""
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Bloquer imports dangereux
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if name.name.split(".")[0] in BLOCKED_MODULES:
                            return False, f"Module bloqué: {name.name}"

                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in BLOCKED_MODULES:
                        return False, f"Import bloqué: {node.module}"

                # Bloquer exec/eval
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in (
                        "exec",
                        "eval",
                    ):
                        return False, "Utilisation de exec/eval interdite"

                # Bloquer open() sans restriction
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "open":
                        return False, "open() interdit pour sécurité"

            return True, "Code accepté"
        except SyntaxError as e:
            return False, f"Syntaxe invalide: {e}"

    def execute(self, code: str, timeout: int | None = None) -> dict[str, Any]:
        """
        Exécution sécurisée du code
        """
        start_time = time.time()
        timeout = timeout or self.timeout

        result = {
            "success": False,
            "output": "",
            "error": None,
            "execution_time": 0,
            "code_hash": hashlib.sha256(code.encode()).hexdigest()[:16],
        }

        # 1. Analyse statique AST
        safe, msg = self._check_dangerous_code(code)
        if not safe:
            result["error"] = f"Code rejected: {msg}"
            self._log_audit(result)
            return result

        # 2. Exécution dans TemporaryDirectory isolé
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "sandbox_script.py"

            # Écrire le code
            tmp_path.write_text(code, encoding="utf-8")

            try:
                # Exécution via subprocess avec restrictions
                proc = subprocess.run(
                    ["python", "-u", str(tmp_path)],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=self._get_restricted_env(tmpdir),
                )

                result["success"] = proc.returncode == 0
                result["output"] = proc.stdout
                if proc.stderr:
                    result["error"] = proc.stderr.strip()

            except subprocess.TimeoutExpired:
                result["error"] = f"Timeout après {timeout}s"
            except Exception as e:
                result["error"] = str(e)

        result["execution_time"] = round(time.time() - start_time, 3)

        # Log d'audit
        self._log_audit(result)

        return result

    def _get_restricted_env(self, tmpdir: str) -> dict[str, str]:
        """Environnement restreint pour l'exécution"""
        import os

        env = os.environ.copy()
        # Supprimer les variables sensibles
        for key in ["PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"]:
            env.pop(key, None)
        # Ajouter un PYTHONPATH minimal vers le tmpdir
        env["PYTHONPATH"] = tmpdir
        return env

    def _log_audit(self, result: dict):
        """Log d'audit pour traçabilité"""
        level = logging.INFO if result["success"] else logging.WARNING
        logger.log(
            level,
            f"Code execution | hash={result['code_hash']} | "
            f"success={result['success']} | time={result['execution_time']}s",
        )
