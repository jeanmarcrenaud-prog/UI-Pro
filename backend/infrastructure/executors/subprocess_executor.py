"""
SubprocessExecutor: executes Python code in an isolated child process.

The code is written to a temp file and executed via sys.executable.
stdout/stderr are captured through pipes.
The subprocess is killed on timeout.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
import time

from .base import BaseExecutor, ExecutionResult

logger = logging.getLogger(__name__)


class SubprocessExecutor(BaseExecutor):
    """Execute code in an isolated subprocess via create_subprocess_exec.

    True process-level isolation:
    - Runs in a separate Python process (can't access app memory)
    - stdout/stderr captured via pipes
    - Temp file cleaned up after execution
    - Timeout kills the subprocess
    """

    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds

    async def execute(
        self,
        code: str,
        filename: str = "main.py",
    ) -> ExecutionResult:
        fd = None
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=".py", prefix="sandbox_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(code)
            fd = None

            start = time.perf_counter()
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout_seconds
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                if proc.returncode is None:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    await proc.wait()
                elapsed_ms = (time.perf_counter() - start) * 1000
                return ExecutionResult(
                    False,
                    error=(
                        f"Subprocess execution timed out after {self.timeout_seconds}s "
                        f"(EXECUTOR_TIMEOUT). Simplify the code or increase the timeout."
                    ),
                    execution_time_ms=elapsed_ms,
                    sandbox_type="subprocess",
                )

            elapsed_ms = (time.perf_counter() - start) * 1000
            out_text = stdout.decode("utf-8", errors="replace") if stdout else ""
            err_text = stderr.decode("utf-8", errors="replace") if stderr else ""

            if proc.returncode == 0:
                return ExecutionResult(
                    True,
                    output=out_text,
                    execution_time_ms=elapsed_ms,
                    sandbox_type="subprocess",
                )
            else:
                # Defense in depth: if stderr is empty for any reason, surface
                # the exit code so the user never gets a silent empty failure.
                return ExecutionResult(
                    False,
                    error=err_text or f"Subprocess exited with code {proc.returncode} (no stderr captured)",
                    execution_time_ms=elapsed_ms,
                    sandbox_type="subprocess",
                )

        finally:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
