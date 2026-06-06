"""Tests for P3#2: executing_node must never return an empty error.

The original bug: ``asyncio.TimeoutError`` has ``str(e) == ''`` in Python.
The outer ``asyncio.wait_for(executor.run_files_async(...), timeout=...)``
inside ``executing_node`` was catching the cancellation as a generic
``Exception as e`` and copying ``str(e)`` — an empty string — into
``state["execution_result"]["error"]``. The user saw a blank failure block
with no indication of what went wrong.

These tests exercise ``executing_node`` directly (no live backend needed)
and verify that every failure path produces a non-empty, actionable error
message in both ``state["execution_result"]["error"]`` and the
user-facing assistant summary.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fake_execution_result(success: bool, error: str = "", output: str = "") -> MagicMock:
    """Build a mock that quacks like the return of run_files_async."""
    mock = MagicMock()
    mock.success = success
    mock.error = error
    mock.output = output
    return mock


class TestExecutingNodeTimeout:
    """The original P3#2 root cause: outer wait_for fires."""

    @pytest.mark.asyncio
    async def test_outer_wait_for_timeout_yields_non_empty_error(self):
        """When the outer wait_for times out, error MUST be non-empty.

        Before the fix: ``str(asyncio.TimeoutError()) == ''`` was copied
        into state, giving the user a blank failure block.
        After the fix: a meaningful message names the configured timeout.
        """
        from backend.domain.core.langgraph import nodes

        async def _slow_coro(*_args: Any, **_kwargs: Any) -> None:
            await asyncio.sleep(30)

        fake_service = MagicMock()
        fake_service.run_files_async = _slow_coro

        state: dict[str, Any] = {
            "code": {"files": {"main.py": "print('hi')"}},
            "messages": [],
            "attempt": 0,
            "max_attempts": 3,
        }

        with patch.object(nodes, "settings", MagicMock(executor_timeout=2)):
            with patch(
                "backend.infrastructure.code_execution.CodeExecutionService",
                lambda *a, **kw: fake_service,
            ):
                start = time.perf_counter()
                result = await nodes.executing_node(state)
                elapsed = time.perf_counter() - start

        # Should have cancelled at the configured timeout, not waited the full 30s
        assert elapsed < 5, f"should have timed out near 2s, took {elapsed:.2f}s"

        exec_result = result["execution_result"]
        assert exec_result["success"] is False
        assert exec_result["error"], (
            f"FAIL: error is empty — the P3#2 regression. Got: {exec_result['error']!r}"
        )
        assert "timeout" in exec_result["error"].lower()
        assert "2" in exec_result["error"]  # duration must appear

        # User-facing summary must also mention the error
        last_msg = result["messages"][-1]
        assert last_msg["role"] == "assistant"
        assert "Error" in last_msg["content"] or "timeout" in last_msg["content"].lower()


class TestExecutingNodeSuccess:
    """Regression: a real successful run still produces a success summary."""

    @pytest.mark.asyncio
    async def test_successful_execution_emits_success_summary(self):
        from backend.domain.core.langgraph import nodes

        fake_service = MagicMock()
        fake_service.run_files_async = AsyncMock(
            return_value=_fake_execution_result(
                success=True, output="hello world\n"
            )
        )

        state: dict[str, Any] = {
            "code": {"files": {"main.py": "print('hello world')"}},
            "messages": [],
            "attempt": 0,
            "max_attempts": 3,
        }

        with patch(
            "backend.infrastructure.code_execution.CodeExecutionService",
            lambda *a, **kw: fake_service,
        ):
            result = await nodes.executing_node(state)

        assert result["execution_result"]["success"] is True
        last_msg = result["messages"][-1]
        assert "✅" in last_msg["content"]
        assert "hello world" in last_msg["content"]
        assert "Attempt 1/3" in last_msg["content"]


class TestExecutingNodeFailure:
    """Regression: an upstream crash surfaces the traceback in the summary."""

    @pytest.mark.asyncio
    async def test_upstream_traceback_surfaces_in_summary(self):
        from backend.domain.core.langgraph import nodes

        fake_service = MagicMock()
        fake_service.run_files_async = AsyncMock(
            return_value=_fake_execution_result(
                success=False,
                error="TypeError: 'NoneType' object is not subscriptable",
                output="=== main.py ===\n",
            )
        )

        state: dict[str, Any] = {
            "code": {"files": {"main.py": "x = None\nprint(x[0])"}},
            "messages": [],
            "attempt": 0,
            "max_attempts": 3,
        }

        with patch(
            "backend.infrastructure.code_execution.CodeExecutionService",
            lambda *a, **kw: fake_service,
        ):
            result = await nodes.executing_node(state)

        assert result["execution_result"]["success"] is False
        assert result["execution_result"]["error"]  # non-empty
        last_msg = result["messages"][-1]
        assert "TypeError" in last_msg["content"]
        assert "❌" in last_msg["content"]
        assert "attempt 1/3" in last_msg["content"]

    @pytest.mark.asyncio
    async def test_upstream_empty_error_gets_fallback(self):
        """Defense in depth: if upstream somehow returns success=False with
        an empty error, the summary still gets a meaningful message rather
        than a silent blank block."""
        from backend.domain.core.langgraph import nodes

        fake_service = MagicMock()
        fake_service.run_files_async = AsyncMock(
            return_value=_fake_execution_result(success=False, error="", output="")
        )

        state: dict[str, Any] = {
            "code": {"files": {"main.py": "print('hi')"}},
            "messages": [],
            "attempt": 0,
            "max_attempts": 3,
        }

        with patch(
            "backend.infrastructure.code_execution.CodeExecutionService",
            lambda *a, **kw: fake_service,
        ):
            result = await nodes.executing_node(state)

        last_msg = result["messages"][-1]
        # The summary should not be a silent blank block. It should
        # at least say "no error message" or similar, so the user
        # knows something went wrong.
        assert "❌" in last_msg["content"]
        assert "Execution failed" in last_msg["content"]


class TestExecutingNodeNoFiles:
    """Edge case: empty state["code"] → executor returns 'No files to execute'."""

    @pytest.mark.asyncio
    async def test_no_files_yields_meaningful_error(self):
        from backend.domain.core.langgraph import nodes

        fake_service = MagicMock()
        fake_service.run_files_async = AsyncMock(
            return_value=_fake_execution_result(
                success=False, error="No files to execute"
            )
        )

        state: dict[str, Any] = {
            "code": {},
            "messages": [],
            "attempt": 0,
            "max_attempts": 3,
        }

        with patch(
            "backend.infrastructure.code_execution.CodeExecutionService",
            lambda *a, **kw: fake_service,
        ):
            result = await nodes.executing_node(state)

        assert result["execution_result"]["error"] == "No files to execute"
        last_msg = result["messages"][-1]
        assert "No files" in last_msg["content"]


class TestExecutingNodeGenericException:
    """Defense in depth: a generic exception with an empty str() doesn't
    produce a blank error message."""

    @pytest.mark.asyncio
    async def test_exception_with_empty_str_still_has_type_name(self):
        from backend.domain.core.langgraph import nodes

        class _NoStrError(Exception):
            def __str__(self) -> str:
                return ""

        async def _raising_coro(*_args: Any, **_kwargs: Any) -> None:
            raise _NoStrError()

        fake_service = MagicMock()
        fake_service.run_files_async = _raising_coro

        state: dict[str, Any] = {
            "code": {"files": {"main.py": "raise SomeError()"}},
            "messages": [],
            "attempt": 0,
            "max_attempts": 3,
        }

        with patch(
            "backend.infrastructure.code_execution.CodeExecutionService",
            lambda *a, **kw: fake_service,
        ):
            result = await nodes.executing_node(state)

        err = result["execution_result"]["error"]
        assert err, "error MUST be non-empty even when the exception's str() is empty"
        assert "_NoStrError" in err
