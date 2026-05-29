"""
Abstract base class for code executors.
Each executor runs Python code in an isolated environment.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ExecutionResult:
    """Résultat d'une exécution de code.

    Utilisé par tous les backends (subprocess, Docker).
    Converti en dict avant stockage dans AgentState.
    """

    success: bool
    output: str = ""
    error: str = ""
    execution_time_ms: float = 0.0
    review_result: Any = None  # ReviewResult, lazy-imported
    sandbox_type: str = "subprocess"  # "subprocess" or "docker"

    def to_dict(self) -> dict[str, Any]:
        """Conversion vers dict (pour stockage dans AgentState)."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


class BaseExecutor(ABC):
    """Interface commune pour tous les backends d'exécution.

    Implémentations:
    - SubprocessExecutor: processus Python isolé (fallback par défaut)
    - DockerExecutor: conteneur Docker éphémère (recommandé si Docker disponible)
    """

    @abstractmethod
    async def execute(
        self,
        code: str,
        filename: str = "main.py",
    ) -> ExecutionResult:
        """Exécute un fichier de code dans l'environnement isolé.

        Args:
            code: Code Python à exécuter
            filename: Nom du fichier (pour le débogage)

        Returns:
            ExecutionResult avec success, output, error, execution_time_ms
        """
        ...

    async def run_files(self, files: dict[str, Any]) -> ExecutionResult:
        """Exécute plusieurs fichiers séquentiellement.

        Chaque fichier est exécuté via self.execute().
        Si un fichier échoue, les suivants sont ignorés.
        """
        if not isinstance(files, dict):
            return ExecutionResult(
                False, error=f"Expected dict, got {type(files).__name__}"
            )

        file_dict = files.get("files", files)
        if not file_dict or not isinstance(file_dict, dict):
            return ExecutionResult(False, error="No files to execute")

        import logging

        logger = logging.getLogger(__name__)

        results: list[dict[str, Any]] = []
        all_success = True

        for filename, code in file_dict.items():
            if not isinstance(code, str):
                logger.warning("Skipping %s: not a string", filename)
                continue
            logger.info("Executing file: %s", filename)
            result = await self.execute(code, filename)
            results.append(
                {
                    "filename": filename,
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "execution_time_ms": result.execution_time_ms,
                }
            )
            if not result.success:
                all_success = False
                break

        combined_output = "\n".join(
            f"=== {r['filename']} ===\n{r['output'] or r['error']}" for r in results
        )

        return ExecutionResult(
            success=all_success,
            output=combined_output,
            error="" if all_success else results[-1]["error"],
            execution_time_ms=sum(r["execution_time_ms"] for r in results),
            sandbox_type=self.__class__.__name__.replace("Executor", "").lower(),
        )
