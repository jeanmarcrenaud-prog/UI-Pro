"""Tests for sandbox timeout alignment.

The single source of truth for code execution timeouts is
``settings.executor_timeout``. ``CodeExecutionService`` must propagate it
to the underlying executor (SubprocessExecutor / DockerExecutor) so that
changing ``EXECUTOR_TIMEOUT`` in Settings actually kills the process at the
configured value (regression: ``TIMEOUT_SECONDS = 5`` was hardcoded).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.domain.settings import settings
from backend.infrastructure.code_execution import CodeExecutionService


def test_service_defaults_to_settings_executor_timeout() -> None:
    """No explicit timeout → service uses settings.executor_timeout."""
    svc = CodeExecutionService()
    assert svc.timeout_seconds == settings.executor_timeout


def test_service_explicit_timeout_overrides_settings() -> None:
    """Explicit timeout_seconds wins over settings."""
    svc = CodeExecutionService(timeout_seconds=42)
    assert svc.timeout_seconds == 42


def test_service_propagates_timeout_to_executor() -> None:
    """get_executor must receive the same timeout as the service."""
    fake_executor = MagicMock()
    fake_executor.timeout_seconds = 60

    with patch(
        "backend.infrastructure.code_execution.get_executor",
        return_value=fake_executor,
    ) as mock_get_executor:
        svc = CodeExecutionService(timeout_seconds=60)

    mock_get_executor.assert_called_once_with(
        preferred=None, timeout_seconds=60
    )
    assert getattr(svc._executor, "timeout_seconds") == 60


def test_service_propagates_timeout_to_secure_executor() -> None:
    """SecureCodeExecutor (AST analysis) receives the same timeout."""
    svc = CodeExecutionService(timeout_seconds=30)
    assert svc._secure_executor.timeout == 30


def test_execute_timeout_error_mentions_configured_value() -> None:
    """Timeout error message must name the configured timeout (not 5s)."""
    fake_executor = MagicMock()

    async def _hang(*_args: object, **_kwargs: object) -> object:
        import asyncio

        await asyncio.sleep(30)
        return None

    fake_executor.execute = _hang

    with patch(
        "backend.infrastructure.code_execution.get_executor",
        return_value=fake_executor,
    ):
        svc = CodeExecutionService(timeout_seconds=3)

    import asyncio

    result = asyncio.run(svc.execute("print('hi')"))
    assert result.success is False
    assert "3s" in result.error
    assert "EXECUTOR_TIMEOUT" in result.error