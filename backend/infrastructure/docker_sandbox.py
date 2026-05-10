# services/docker_sandbox.py - Secure Docker-based code execution sandbox
"""
Secure sandbox using Docker containers for LLM-generated code execution.
Provides strong isolation with resource limits and security hardening.
"""

import docker
import time
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    success: bool
    output: str = ""
    error: str = ""
    execution_time_ms: float = 0.0
    container_id: Optional[str] = None
    resources_used: Dict[str, Any] = None


class DockerSandbox:
    """
    Secure sandbox using Docker containers for LLM-generated code.
    
    Security features:
    - Process, filesystem, and network isolation
    - CPU and memory resource limits
    - No internet access (network_disabled=True)
    - Read-only filesystem (read_only=True)
    - Non-root user (nobody)
    - Small tmpfs for temp files
    - Auto-cleanup on exit
    """

    def __init__(
        self,
        image: str = "python:3.11-slim",
        cpu_limit: float = 1.0,      # CPU cores
        memory_limit: str = "512m",  # Memory limit
        timeout_seconds: int = 30,
    ):
        self.image = image
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.timeout_seconds = timeout_seconds
        self.client = None

    def _get_client(self):
        """Lazy Docker client initialization."""
        if self.client is None:
            try:
                self.client = docker.from_env()
            except Exception as e:
                logger.error(f"Failed to connect to Docker: {e}")
                raise RuntimeError("Docker is not available. Please start Docker daemon.")
        return self.client

    def execute(self, code: str, requirements: Optional[List[str]] = None) -> SandboxResult:
        """Execute code in isolated Docker container."""
        start_time = time.time()
        container = None

        try:
            client = self._get_client()

            # Prepare script with output capture
            script = f"""
import sys
import io
import traceback

# Redirect output
output = io.StringIO()
sys.stdout = output
sys.stderr = output

try:
    exec('''{code}''', {{'__builtins__': __builtins__}})
    print("---RESULT---")
    print(output.getvalue())
except Exception as e:
    print("---ERROR---")
    print(traceback.format_exc())
"""

            # Create container with strict security limits
            container = client.containers.run(
                self.image,
                command=["python", "-c", script],
                detach=True,
                mem_limit=self.memory_limit,
                cpu_shares=int(self.cpu_limit * 1024),
                network_disabled=True,      # No internet
                read_only=True,             # Filesystem read-only
                tmpfs={'/tmp': 'size=64m'}, # Small writable tmp
                working_dir="/app",
                user="nobody",              # Non-root user
                remove=True,                # Auto-cleanup
            )

            # Wait with timeout
            try:
                result = container.wait(timeout=self.timeout_seconds)
                logs = container.logs().decode('utf-8')
            except Exception:
                container.kill()
                logs = "Execution timed out."

            # Parse output
            success = result.get('StatusCode', 1) == 0
            
            if "---RESULT---" in logs:
                output = logs.split("---RESULT---")[-1].strip()
                error = ""
            elif "---ERROR---" in logs:
                output = ""
                error = logs.split("---ERROR---")[-1].strip()
            else:
                output = logs.strip()
                error = ""

            return SandboxResult(
                success=success,
                output=output,
                error=error,
                execution_time_ms=(time.time() - start_time) * 1000,
                container_id=container.id[:12] if container else None,
            )

        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")
            return SandboxResult(success=False, error=f"Docker error: {str(e)}")
        except Exception as e:
            logger.error(f"Sandbox execution failed: {e}")
            return SandboxResult(success=False, error=str(e))
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass

    def test_sandbox(self) -> bool:
        """Test if sandbox is working."""
        test_code = "print('Sandbox test successful')"
        result = self.execute(test_code)
        return result.success and "Sandbox test successful" in result.output


# ====================== Singleton ======================

_sandbox: Optional[DockerSandbox] = None


def get_docker_sandbox() -> DockerSandbox:
    global _sandbox
    if _sandbox is None:
        _sandbox = DockerSandbox()
    return _sandbox


__all__ = ["DockerSandbox", "SandboxResult", "get_docker_sandbox"]