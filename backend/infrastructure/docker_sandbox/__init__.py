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
    ):
        self.image = image
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
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
            # Run container
            result = await asyncio.create_subprocess_exec(
                "docker",
                "run",
                "--rm",
                "--memory",
                f"{self.memory_limit_mb}m",
                "--cpus",
                "1.0",
                "--network",
                "none",  # No network access
                "-i",  # Interactive (stdin)
                self.image,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Send input and get output
            stdout, stderr = await result.communicate(
                input=input_data.encode(), timeout=self.timeout_seconds
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


def get_docker_sandbox() -> DockerSandbox:
    """Get the singleton Docker sandbox instance."""
    global _docker_sandbox
    if _docker_sandbox is None:
        _docker_sandbox = DockerSandbox()
    return _docker_sandbox


__all__ = ["DockerExecutionResult", "DockerSandbox", "get_docker_sandbox"]
