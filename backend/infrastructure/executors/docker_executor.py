"""
DockerExecutor: executes Python code in an ephemeral Docker container.

Uses the existing DockerSandbox (docker_sandbox/__init__.py) under the hood.
Provides stronger isolation than SubprocessExecutor:
- Separate filesystem, process tree, network namespace
- Memory/CPU limits via Docker flags
- Non-root user inside container
- Ephemeral container (--rm), auto-cleaned
"""

from __future__ import annotations

import logging

from backend.infrastructure.docker_sandbox import DockerSandbox, get_docker_sandbox

from .base import BaseExecutor, ExecutionResult

logger = logging.getLogger(__name__)


class DockerExecutor(BaseExecutor):
    """Execute code in an ephemeral Docker container.

    Wraps DockerSandbox. If Docker is not available, raises on first execute
    so the caller (CodeExecutionService) can fall back to SubprocessExecutor.

    Supports advanced isolation features:
    - gVisor runtime (--runtime runsc) for user-space kernel sandboxing
    - Configurable network access (disabled by default)
    - PIDs limit to prevent fork bombs
    - CPU shares and memory limits for resource control
    """

    def __init__(
        self,
        timeout_seconds: int = 30,
        memory_limit_mb: int = 512,
        auto_build: bool = False,
        use_gvisor: bool = False,
        pids_limit: int = 80,
        cpu_shares: int = 512,
        network_enabled: bool = False,
    ):
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.use_gvisor = use_gvisor
        self.pids_limit = pids_limit
        self.cpu_shares = cpu_shares
        self.network_enabled = network_enabled
        self._sandbox: DockerSandbox | None = None
        self._available: bool | None = None  # None = unset, True/False = cached
        self._gvisor_checked: bool = False

        if use_gvisor:
            self._check_gvisor_available()

        if auto_build:
            sandbox = self._get_sandbox()
            if sandbox and not sandbox._is_docker_available():
                logger.warning("Docker not available — DockerExecutor will fail at runtime")
            elif sandbox:
                built = sandbox._build_image()
                if built:
                    logger.info("Docker sandbox image built successfully")
                else:
                    logger.warning("Failed to build Docker sandbox image")

    def _check_gvisor_available(self) -> bool:
        """Vérifie si le runtime gVisor (runsc) est disponible via docker info."""
        if self._gvisor_checked:
            return True
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "info", "--format", "{{json .Runtimes}}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and "runsc" in result.stdout:
                logger.info("gVisor (runsc) détecté et disponible")
                self._gvisor_checked = True
                return True
            else:
                logger.warning(
                    "gVisor (runsc) demandé mais non détecté dans docker info. "
                    "Le runtime par défaut sera utilisé. "
                    "Installez gVisor: https://gvisor.dev/docs/"
                )
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning("Impossible de vérifier gVisor: %s", e)
            return False

    def _get_sandbox(self) -> DockerSandbox | None:
        if self._sandbox is None:
            try:
                self._sandbox = get_docker_sandbox(
                    timeout_seconds=self.timeout_seconds,
                    memory_limit_mb=self.memory_limit_mb,
                    use_gvisor=self.use_gvisor,
                    pids_limit=self.pids_limit,
                    cpu_shares=self.cpu_shares,
                    network_enabled=self.network_enabled,
                )
            except Exception as e:
                logger.warning("Failed to get Docker sandbox: %s", e)
                return None
        return self._sandbox

    async def is_available(self) -> bool:
        """Check if Docker is available (cached)."""
        if self._available is not None:
            return self._available
        sandbox = self._get_sandbox()
        if sandbox is None:
            self._available = False
            return False
        self._available = sandbox._is_docker_available()
        return self._available

    async def execute(
        self,
        code: str,
        filename: str = "main.py",
    ) -> ExecutionResult:
        sandbox = self._get_sandbox()
        if sandbox is None:
            return ExecutionResult(
                False,
                error="Docker sandbox not initialized",
                sandbox_type="docker",
            )

        try:
            result = await sandbox.execute(code, "python")

            return ExecutionResult(
                success=result.success,
                output=result.output,
                error=result.error,
                execution_time_ms=result.execution_time_ms,
                sandbox_type="docker",
            )
        except Exception as e:
            logger.exception("Docker execution failed")
            return ExecutionResult(
                False,
                error=f"Docker sandbox error: {e!s}",
                sandbox_type="docker",
            )
