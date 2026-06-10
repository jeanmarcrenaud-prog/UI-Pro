"""
Abstract base class for code executors.
Each executor runs Python code in an isolated environment.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Streaming callback type: (line: str, channel: "stdout" | "stderr") -> None
OutputCallback = Callable[[str, str], None]


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
        output_callback: OutputCallback | None = None,
    ) -> ExecutionResult:
        """Exécute un fichier de code dans l'environnement isolé.

        Args:
            code: Code Python à exécuter
            filename: Nom du fichier (pour le débogage)
            output_callback: If provided, called as ``cb(line, channel)``
                for each output line in real-time (streaming mode).

        Returns:
            ExecutionResult avec success, output, error, execution_time_ms
        """
        ...

    async def run_files(
        self,
        files: dict[str, Any],
        output_callback: Callable[[str, str], None] | None = None,
    ) -> ExecutionResult:
        """Exécute plusieurs fichiers séquentiellement.

        Chaque fichier est exécuté via self.execute().
        Si un fichier échoue, les suivants sont ignorés.

        Args:
            files: Dict of ``{filename: source_code}``.
            output_callback: Optional callback ``(line, channel)`` forwarded
                to each ``execute()`` call for real-time output streaming.
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
            result = await self.execute(code, filename, output_callback=output_callback)
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

        # Defense in depth: if any file failed, never return an empty error.
        # Empty error fields propagate to the user as a silent failure (P3#2).
        if all_success:
            final_error = ""
        else:
            last = results[-1]
            if last["error"]:
                final_error = last["error"]
            elif last["output"]:
                # Subprocess produced stdout but failed — surface that the file
                # returned non-zero with no stderr, so the user isn't left guessing.
                final_error = (
                    f"{last['filename']} exited with a non-zero status "
                    f"(no stderr captured). Partial output: {last['output'][:200]}"
                )
            else:
                final_error = (
                    f"{last['filename']} exited with a non-zero status "
                    f"and no output or stderr captured. Check executor logs."
                )

        return ExecutionResult(
            success=all_success,
            output=combined_output,
            error=final_error,
            execution_time_ms=sum(r["execution_time_ms"] for r in results),
            sandbox_type=self.__class__.__name__.replace("Executor", "").lower(),
        )
