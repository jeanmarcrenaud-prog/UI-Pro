"""
SubprocessExecutor: executes code in an isolated child process.

Supports Python, PowerShell, Node.js, and Bash via filename extension detection.
The code is written to a temp file and executed via the appropriate interpreter.
stdout/stderr are captured through pipes.
The subprocess is killed on timeout.

Supports two modes:
  - **Batch** (default): uses ``proc.communicate()``, returns all output at end.
  - **Streaming** (when *output_callback* is provided): reads line by line and
    calls *output_callback(line, channel)* for each line in real-time.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from .base import BaseExecutor, ExecutionResult

logger = logging.getLogger(__name__)

# Type alias: callback(line_content, channel)
OutputCallback = Callable[[str, str], None]

# Language detection by filename extension
_LANG_MAP: dict[str, dict] = {
    ".ps1": {
        "interpreter": "powershell",
        "args": ["-ExecutionPolicy", "Bypass", "-File"],
        "suffix": ".ps1",
    },
    ".psm1": {
        "interpreter": "powershell",
        "args": ["-ExecutionPolicy", "Bypass", "-File"],
        "suffix": ".ps1",
    },
    ".psd1": {
        "interpreter": "powershell",
        "args": ["-ExecutionPolicy", "Bypass", "-File"],
        "suffix": ".ps1",
    },
    ".sh": {
        "interpreter": "bash",
        "args": [],
        "suffix": ".sh",
    },
    ".bash": {
        "interpreter": "bash",
        "args": [],
        "suffix": ".sh",
    },
    ".js": {
        "interpreter": "node",
        "args": [],
        "suffix": ".js",
    },
    ".mjs": {
        "interpreter": "node",
        "args": [],
        "suffix": ".mjs",
    },
    ".ts": {
        "interpreter": "node",
        "args": [],
        "suffix": ".js",
    },
    ".bat": {
        "interpreter": "cmd",
        "args": ["/c"],
        "suffix": ".bat",
    },
    ".cmd": {
        "interpreter": "cmd",
        "args": ["/c"],
        "suffix": ".cmd",
    },
}

_DEFAULT_LANG = {
    "interpreter": sys.executable,
    "args": ["-u"],
    "suffix": ".py",
}


def _get_lang_config(filename: str) -> dict:
    ext = Path(filename).suffix.lower()
    return _LANG_MAP.get(ext, _DEFAULT_LANG)


class SubprocessExecutor(BaseExecutor):
    """Execute code in an isolated subprocess via create_subprocess_exec.

    True process-level isolation:
    - Runs in a separate process (can't access app memory)
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
        output_callback: OutputCallback | None = None,
    ) -> ExecutionResult:
        fd = None
        path = None
        try:
            lang_cfg = _get_lang_config(filename)
            suffix = lang_cfg["suffix"]
            fd, path = tempfile.mkstemp(suffix=suffix, prefix="sandbox_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(code)
            fd = None

            start = time.perf_counter()
            cmd = [lang_cfg["interpreter"]] + lang_cfg["args"] + [path]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            if output_callback is not None:
                return await self._execute_streaming(
                    proc, start, output_callback
                )
            else:
                return await self._execute_batch(proc, start)

        finally:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    # — Batch mode (original) ————————————————————————————————————————————

    async def _execute_batch(
        self, proc: asyncio.subprocess.Process, start: float
    ) -> ExecutionResult:
        """Original ``proc.communicate()`` path — no streaming."""
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
            return ExecutionResult(
                False,
                error=err_text
                or f"Subprocess exited with code {proc.returncode} (no stderr captured)",
                execution_time_ms=elapsed_ms,
                sandbox_type="subprocess",
            )

    # ── Streaming mode (line-by-line) ──────────────────────────────────

    async def _execute_streaming(
        self,
        proc: asyncio.subprocess.Process,
        start: float,
        callback: OutputCallback,
    ) -> ExecutionResult:
        """Read stdout/stderr line-by-line, calling *callback* for each line.

        Two concurrent tasks read the pipes so neither backs up.
        All output is also collected for the ``ExecutionResult``.
        """
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        async def _read_pipe(
            stream: asyncio.StreamReader | None,
            channel: str,
            dest: list[str],
        ) -> None:
            """Read a single pipe line-by-line until EOF."""
            if stream is None:
                return
            while True:
                try:
                    line_bytes = await asyncio.wait_for(
                        stream.readline(), timeout=self.timeout_seconds
                    )
                except asyncio.TimeoutError:
                    # No data yet — keep polling (the overall watcher above
                    # will enforce the global timeout).
                    continue
                except (BrokenPipeError, ConnectionResetError, ValueError):
                    break

                if not line_bytes:  # EOF
                    break
                text = line_bytes.decode("utf-8", errors="replace").rstrip("\n\r")
                if text:
                    dest.append(text)
                    try:
                        callback(text, channel)
                    except Exception:
                        logger.exception(
                            "output_callback failed for %s line", channel
                        )

        # Launch concurrent readers
        reader_tasks = [
            asyncio.create_task(_read_pipe(proc.stdout, "stdout", stdout_lines)),
            asyncio.create_task(_read_pipe(proc.stderr, "stderr", stderr_lines)),
        ]

        # Wait for BOTH readers to complete (EOF) or timeout.
        # ``ALL_COMPLETED`` ensures we don't cancel one pipe early.
        done, pending = await asyncio.wait(
            reader_tasks,
            timeout=self.timeout_seconds + 5,
            return_when=asyncio.ALL_COMPLETED,
        )

        # Timeout path: if any readers are still pending the process hung.
        if pending:
            for t in pending:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
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

        # Normal path — both readers reached EOF.  Collect exit status.
        if proc.returncode is None:
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Subprocess did not exit after all pipes closed")

        elapsed_ms = (time.perf_counter() - start) * 1000
        out_text = "\n".join(stdout_lines)
        err_text = "\n".join(stderr_lines)

        if proc.returncode == 0:
            return ExecutionResult(
                True,
                output=out_text,
                execution_time_ms=elapsed_ms,
                sandbox_type="subprocess",
            )
        else:
            return ExecutionResult(
                False,
                error=err_text
                or f"Subprocess exited with code {proc.returncode} (no stderr captured)",
                output=out_text,
                execution_time_ms=elapsed_ms,
                sandbox_type="subprocess",
            )
