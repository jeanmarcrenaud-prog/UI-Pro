"""
Sandbox sécurisé pour exécution de code Python généré par LLM.

Composé de deux couches:
1. CodeExecutionService: orchestration + sécurité (AST, review) + sélection du backend
2. Executors (backend/infrastructure/executors/): exécution isolée (subprocess ou Docker)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.domain.core.code_review import review_code
from backend.infrastructure.secure_executor import SecureCodeExecutor

from .executors import BaseExecutor, ExecutionResult, get_executor

logger = logging.getLogger(__name__)


class CodeExecutionService:
    """Orchestrateur d'exécution sécurisée.

    1. Analyse statique (AST) du code
    2. Revue de sécurité (review_code)
    3. Délégation au backend d'exécution (SubprocessExecutor / DockerExecutor)
    4. Timeout et gestion d'erreurs
    """

    TIMEOUT_SECONDS = 5

    def __init__(self, backend: BaseExecutor | str | None = None):
        # Secure executor with AST analysis (Python only)
        self._secure_executor = SecureCodeExecutor(
            timeout=self.TIMEOUT_SECONDS, memory_limit_mb=512
        )

        # Backend d'exécution
        if isinstance(backend, BaseExecutor):
            self._executor = backend
        else:
            self._executor = get_executor(
                preferred=backend, timeout_seconds=self.TIMEOUT_SECONDS
            )

    @property
    def backend_name(self) -> str:
        """Nom du backend actif (pour logging/metrics)."""
        return type(self._executor).__name__.replace("Executor", "").lower()

    async def execute(
        self,
        code: str,
        globals_dict: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Exécute du code Python de manière sécurisée.

        1. Validation du code vide
        2. Analyse statique AST (SecureCodeExecutor)
        3. Revue de sécurité (review_code)
        4. Exécution isolée via le backend sélectionné
        """
        if not code.strip():
            return ExecutionResult(False, error="empty code")

        # Static analysis via AST (catches dangerous imports, exec/eval, open())
        ast_safe, ast_msg = self._secure_executor._check_dangerous_code(code)
        if not ast_safe:
            return ExecutionResult(
                False,
                error=f"Code rejected: {ast_msg}",
            )

        review = review_code(code)

        if not review.success:
            return ExecutionResult(
                False,
                error="static review failed",
                review_result=review,
            )

        try:
            result = await asyncio.wait_for(
                self._executor.execute(code),
                timeout=self.TIMEOUT_SECONDS,
            )
            result.review_result = review
            return result

        except asyncio.TimeoutError:
            return ExecutionResult(False, error="execution timeout")

        except Exception as exc:
            logger.exception("execution failed")
            return ExecutionResult(False, error=str(exc))

    async def run_files_async(self, files: dict[str, Any]) -> ExecutionResult:
        """Execute multiple files from a {"files": {"name.py": "content"}} dict.

        Délègue au backend (SubprocessExecutor ou DockerExecutor).
        """
        return await self._executor.run_files(files)

    def run(self, files: dict[str, Any]) -> ExecutionResult:
        """Execute multiple files (sync wrapper around run_files_async).

        For async contexts, prefer await service.run_files_async(files).
        """
        return asyncio.run(self.run_files_async(files))
