"""
multi_lang_executor.py - Exécuteur multi-langage avec détection automatique
"""

import hashlib
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional


class MultiLangExecutor:
    """
    Exécuteur sécurisé qui détecte le langage et exécute le code correspondant.
    """

    LANG_CONFIG = {
        "python": {
            "extension": ".py",
            "command": ["python", "-u"],
            "timeout": 30,
        },
        "javascript": {
            "extension": ".js",
            "command": ["node"],
            "timeout": 20,
        },
        "bash": {
            "extension": ".sh",
            "command": ["bash"],
            "timeout": 15,
        },
        "shell": {
            "extension": ".sh",
            "command": ["bash"],
            "timeout": 15,
        }
    }

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    def _detect_language(self, code: str, filename: Optional[str] = None) -> str:
        """Détection intelligente du langage"""
        
        code_stripped = code.strip()
        first_line = code_stripped.split('\n')[0].strip()

        # 1. Shebang explicite
        if first_line.startswith("#!"):
            if "python" in first_line:
                return "python"
            if "node" in first_line or "javascript" in first_line:
                return "javascript"
            if "bash" in first_line or "sh" in first_line:
                return "bash"

        # 2. Détection par mots-clés
        if re.search(r'^(import |from |def |class |print\(|async def|if __name__)', code_stripped):
            return "python"
        
        if re.search(r'^(console\.log|function |const |let |var |export |import |require\(|module\.exports)', code_stripped):
            return "javascript"
        
        if re.search(r'^(echo |ls |cat |mkdir |rm |grep |sed |awk |chmod |export |source )', code_stripped):
            return "bash"

        # 3. Par extension de fichier
        if filename:
            ext = Path(filename).suffix.lower()
            if ext == '.py':
                return "python"
            if ext in ['.js', '.mjs', '.ts']:
                return "javascript"
            if ext in ['.sh', '.bash']:
                return "bash"

        # Par défaut Python
        return "python"

    def execute(self, code: str, filename: Optional[str] = None, timeout: Optional[int] = None) -> Dict[str, Any]:
        start_time = time.time()
        lang = self._detect_language(code, filename)
        
        result = {
            "success": False,
            "language": lang,
            "output": "",
            "error": None,
            "execution_time": 0,
            "code_hash": hashlib.sha256(code.encode()).hexdigest()[:12]
        }

        config = self.LANG_CONFIG.get(lang, self.LANG_CONFIG["python"])
        effective_timeout = timeout or config["timeout"]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            script_path = tmp_path / f"script{config['extension']}"

            # Ajout du shebang pour Bash
            if lang in ["bash", "shell"] and not code.strip().startswith("#!"):
                code = f"#!/bin/bash\n\n{code}"

            script_path.write_text(code, encoding="utf-8")
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
                
                if proc.stderr:
                    result["error"] = proc.stderr.strip()

            except subprocess.TimeoutExpired:
                result["error"] = f"Timeout après {effective_timeout} secondes"
            except FileNotFoundError:
                result["error"] = f"Interpréteur {lang} non trouvé (installez node, bash)"
            except Exception as e:
                result["error"] = str(e)

        result["execution_time"] = round(time.time() - start_time, 3)
        return result