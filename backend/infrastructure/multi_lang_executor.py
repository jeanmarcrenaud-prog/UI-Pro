"""
multi_lang_executor.py - Exécuteur multi-langage avec détection Pygments
"""

import hashlib
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from pygments.lexers import guess_lexer, guess_lexer_for_filename
from pygments.util import ClassNotFound


class MultiLangExecutor:
    """
    Exécuteur sécurisé multi-langage utilisant Pygments pour la détection.
    """

    # Mapping Pygments → Configuration d'exécution
    LANG_CONFIG = {
        "python": {
            "name": "python",
            "extension": ".py",
            "command": ["python", "-u"],
            "timeout": 30,
        },
        "javascript": {
            "name": "javascript",
            "extension": ".js",
            "command": ["node"],
            "timeout": 20,
        },
        "typescript": {
            "name": "typescript",
            "extension": ".ts",
            "command": ["node"],
            "timeout": 20,
        },
        "bash": {
            "name": "bash",
            "extension": ".sh",
            "command": ["bash"],
            "timeout": 15,
        },
        "shell": {
            "name": "shell",
            "extension": ".sh",
            "command": ["bash"],
            "timeout": 15,
        },
        "html": {
            "name": "html",
            "extension": ".html",
            "command": None,
            "timeout": 5,
        },
    }

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    def _detect_language(self, code: str, filename: Optional[str] = None) -> str:
        """Détection avancée via Pygments"""
        if not code.strip():
            return "python"

        # 1. Essayer par nom de fichier d'abord (plus fiable)
        if filename:
            try:
                lexer = guess_lexer_for_filename(filename, code[:5000])
                lang_name = lexer.name.lower()
                if "python" in lang_name:
                    return "python"
                if "javascript" in lang_name or "js" in lang_name:
                    return "javascript"
                if "typescript" in lang_name:
                    return "typescript"
                if "bash" in lang_name or "shell" in lang_name:
                    return "bash"
                if "html" in lang_name:
                    return "html"
            except (ClassNotFound, Exception):
                pass

        # 2. Détection par contenu
        try:
            lexer = guess_lexer(code[:10000])
            lang_name = lexer.name.lower()

            mapping = {
                "python": "python",
                "javascript": "javascript",
                "typescript": "typescript",
                "bash": "bash",
                "shell": "bash",
                "html": "html",
                "xml": "html",
            }

            for key, value in mapping.items():
                if key in lang_name:
                    return value

        except (ClassNotFound, Exception):
            pass

        # Fallback
        return "python"

    def execute(self, code: str, filename: Optional[str] = None, timeout: Optional[int] = None) -> Dict[str, Any]:
        start_time = time.time()
        lang = self._detect_language(code, filename)
        
        result: Dict[str, Any] = {
            "success": False,
            "language": lang,
            "output": "",
            "error": None,
            "execution_time": 0,
            "code_hash": hashlib.sha256(code.encode()).hexdigest()[:12]
        }

        config = self.LANG_CONFIG.get(lang, self.LANG_CONFIG["python"])

        if config.get("command") is None:
            result["error"] = f"Langage '{lang}' non exécutable directement"
            result["execution_time"] = round(time.time() - start_time, 3)
            return result

        effective_timeout = timeout or config["timeout"]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            script_path = tmp_path / f"script{config['extension']}"

            # Ajout du shebang pour les shells
            final_code = code
            if lang in ["bash", "shell"] and not code.startswith("#!"):
                final_code = f"#!/bin/bash\n\n{code}"

            script_path.write_text(final_code, encoding="utf-8")
            script_path.chmod(0o755)

            try:
                cmd = config["command"] + [str(script_path)]
                
                proc = subprocess.run(
                    cmd,
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=effective_timeout,
                )

                result["success"] = proc.returncode == 0
                result["output"] = proc.stdout.strip()
                
                if proc.stderr and proc.stderr.strip():
                    result["error"] = proc.stderr.strip()

            except subprocess.TimeoutExpired:
                result["error"] = f"Timeout après {effective_timeout}s"
            except FileNotFoundError as e:
                result["error"] = f"Interpréteur non trouvé pour {lang} ({e})"
            except Exception as e:
                result["error"] = str(e)

        result["execution_time"] = round(time.time() - start_time, 3)
        return result