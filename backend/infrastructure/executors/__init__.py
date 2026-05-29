"""
Executors package — isolated code execution backends.

Provides:
- BaseExecutor: abstract interface
- SubprocessExecutor: isolated subprocess (Python subprocess)
- DockerExecutor: ephemeral Docker container (stronger isolation)
- get_executor(): auto-select backend based on availability
"""

from __future__ import annotations

import logging

from .base import BaseExecutor, ExecutionResult
from .docker_executor import DockerExecutor
from .subprocess_executor import SubprocessExecutor

logger = logging.getLogger(__name__)


def get_executor(
    preferred: str | None = None,
    timeout_seconds: int = 30,
) -> BaseExecutor:
    """Sélectionne le meilleur backend disponible.

    Args:
        preferred: "docker" ou "subprocess". None = auto-détection.
        timeout_seconds: Timeout pour chaque exécution.

    Returns:
        Un executor prêt à l'emploi.

    Stratégie:
        - "docker" explicite → DockerExecutor (lève l'exception si Docker indisponible)
        - "subprocess" explicite → SubprocessExecutor
        - None (auto) → Docker si disponible, sinon SubprocessExecutor
    """
    if preferred == "subprocess":
        logger.info("Executor backend: subprocess (explicit)")
        return SubprocessExecutor(timeout_seconds=timeout_seconds)

    if preferred == "docker":
        logger.info("Executor backend: docker (explicit)")
        return DockerExecutor(
            timeout_seconds=timeout_seconds, auto_build=False
        )

    # Auto-détection
    docker_exec = DockerExecutor(timeout_seconds=timeout_seconds)
    try:
        # Vérification synchrone rapide
        import subprocess
        result = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            timeout=3,
        )
        if result.returncode == 0:
            logger.info("Executor backend: docker (auto-detected)")
            return docker_exec
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    logger.info("Executor backend: subprocess (Docker not available)")
    return SubprocessExecutor(timeout_seconds=timeout_seconds)


__all__ = [
    "BaseExecutor",
    "DockerExecutor",
    "ExecutionResult",
    "SubprocessExecutor",
    "get_executor",
]
