"""
Docker-based sandbox executor for isolated code execution.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Docker image name
DOCKER_IMAGE = "ui-pro-sandbox:latest"
CONTAINER_NAME = "ui-pro-sandbox"


@dataclass
class DockerExecutionResult:
    success: bool
    output: str = ""
    error: str = ""
    execution_time_ms: float = 0.0


class DockerSandbox:
    """Execute code in isolated Docker container."""

    def __init__(
        self,
        image: str = DOCKER_IMAGE,
        timeout_seconds: int = 30,
        memory_limit_mb: int = 512,
        use_gvisor: bool = False,
        pids_limit: int = 80,
        cpu_shares: int = 512,
        network_enabled: bool = False,
    ):
        self.image = image
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.use_gvisor = use_gvisor
        self.pids_limit = pids_limit
        self.cpu_shares = cpu_shares
        self.network_enabled = network_enabled
        self._container_running = False

    def _is_docker_available(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _build_image(self) -> bool:
        """Build the sandbox Docker image."""
        docker_dir = os.path.dirname(__file__)
        try:
            result = subprocess.run(
                ["docker", "build", "-t", self.image, docker_dir],
                capture_output=True,
                timeout=300,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            return False

    async def execute(
        self, code: str, language: str = "python"
    ) -> DockerExecutionResult:
        """Execute code in Docker sandbox."""
        import time

        start_time = time.time()

        # Check Docker availability
        if not self._is_docker_available():
            return DockerExecutionResult(
                success=False,
                error="Docker not available. Install Docker to use sandbox execution.",
            )

        # Prepare input
        input_data = json.dumps({"code": code, "language": language})

        try:
            # Build docker run args dynamically
            docker_args = [
                "docker", "run", "--rm",
                "--memory", f"{self.memory_limit_mb}m",
                "--cpu-shares", str(self.cpu_shares),
                "--pids-limit", str(self.pids_limit),
            ]
            if not self.network_enabled:
                docker_args.extend(["--network", "none"])
            if self.use_gvisor:
                docker_args.extend(["--runtime", "runsc"])
            docker_args.extend(["-i", self.image])

            result = await asyncio.create_subprocess_exec(
                *docker_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Send input and get output
            try:
                stdout, stderr = await asyncio.wait_for(
                    result.communicate(input=input_data.encode()),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Execution timed out after {self.timeout_seconds}s"
                )

            execution_time = (time.time() - start_time) * 1000

            if result.returncode == 0:
                try:
                    output = json.loads(stdout.decode())
                    return DockerExecutionResult(
                        success=output.get("success", False),
                        output=output.get("output", ""),
                        error=output.get("error", ""),
                        execution_time_ms=output.get(
                            "execution_time_ms", execution_time
                        ),
                    )
                except json.JSONDecodeError:
                    return DockerExecutionResult(
                        success=False,
                        output=stdout.decode(),
                        error="Invalid JSON response from sandbox",
                        execution_time_ms=execution_time,
                    )
            else:
                return DockerExecutionResult(
                    success=False,
                    output=stdout.decode(),
                    error=stderr.decode() or "Container execution failed",
                    execution_time_ms=execution_time,
                )

        except asyncio.TimeoutError:
            return DockerExecutionResult(
                success=False,
                error=f"Execution timeout ({self.timeout_seconds}s)",
                execution_time_ms=self.timeout_seconds * 1000,
            )
        except Exception as e:
            logger.error(f"Docker sandbox error: {e}")
            return DockerExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def health_check(self) -> bool:
        """Check if Docker sandbox is healthy."""
        if not self._is_docker_available():
            return False

        try:
            result = await asyncio.create_subprocess_exec(
                "docker",
                "images",
                "-q",
                self.image,
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            return bool(stdout.strip())
        except:
            return False


# Singleton instance
_docker_sandbox: DockerSandbox | None = None


def get_docker_sandbox(**kwargs: Any) -> DockerSandbox:
    """Get the singleton Docker sandbox instance.

    Args:
        **kwargs: Override DockerSandbox defaults (image, timeout_seconds,
                  memory_limit_mb, use_gvisor, pids_limit, cpu_shares, network_enabled)
    """
    global _docker_sandbox
    if _docker_sandbox is None:
        _docker_sandbox = DockerSandbox(**kwargs)
    return _docker_sandbox


__all__ = ["DockerExecutionResult", "DockerSandbox", "get_docker_sandbox"]
