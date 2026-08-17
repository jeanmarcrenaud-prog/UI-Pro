"""Tests for Hermes ACP connection pool."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.infrastructure.llm.errors import LLMConnectionError
from backend.infrastructure.llm.hermes_acp import (
    HermesACPBackend,
    HermesACPConnectionPool,
    get_acp_pool,
    reset_acp_pool_for_tests,
)
from backend.infrastructure.llm.models import ModelConfig


@pytest.fixture(autouse=True)
def _clean_pool():
    reset_acp_pool_for_tests()
    yield
    reset_acp_pool_for_tests()


def _fake_spawn_stack():
    """Patch spawn + connect to return a reusable fake connection."""
    fake_conn = MagicMock()
    fake_conn.initialize = AsyncMock()
    fake_conn.new_session = AsyncMock(return_value=MagicMock(session_id="sess_1"))
    fake_conn.prompt = AsyncMock(return_value=MagicMock())
    fake_conn.close_session = AsyncMock()

    fake_process = MagicMock()
    fake_process.returncode = None  # subprocess still running

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(
        return_value=(MagicMock(), MagicMock(), fake_process)
    )
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    return fake_conn, mock_cm


class TestPoolAcquireRelease:
    def test_second_acquire_reuses_connection(self):
        fake_conn, mock_cm = _fake_spawn_stack()
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=60)

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                c1 = await pool.acquire("hermes", "/tmp")
                await pool.release(c1)
                c2 = await pool.acquire("hermes", "/tmp")
                assert c1 is c2
                assert mock_cm.__aenter__.await_count == 1
                await pool.release(c2)
                await pool.close_all()

        asyncio.run(run())

    def test_discard_on_error_spawns_fresh(self):
        fake_conn, mock_cm = _fake_spawn_stack()
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=60)

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                c1 = await pool.acquire("hermes", "/tmp")
                await pool.release(c1, discard=True)
                c2 = await pool.acquire("hermes", "/tmp")
                assert c1 is not c2
                assert mock_cm.__aenter__.await_count == 2
                await pool.release(c2)
                await pool.close_all()

        asyncio.run(run())

    def test_stats(self):
        fake_conn, mock_cm = _fake_spawn_stack()
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=60)

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                c = await pool.acquire("hermes", "/tmp")
                s = pool.stats()
                assert s["busy"] == 1
                assert s["connections"] == 1
                await pool.release(c)
                assert pool.stats()["idle"] == 1
                await pool.close_all()

        asyncio.run(run())

    def test_dead_process_skipped_at_acquire(self):
        """A connection whose subprocess exited is not reused."""
        fake_conn, mock_cm = _fake_spawn_stack()
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=60)

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                c1 = await pool.acquire("hermes", "/tmp")
                await pool.release(c1)
                # Simulate the subprocess exiting while idle.
                c1.process.returncode = 1
                c2 = await pool.acquire("hermes", "/tmp")
                assert c1 is not c2
                assert mock_cm.__aenter__.await_count == 2
                assert mock_cm.__aexit__.await_count == 1  # dead conn destroyed
                await pool.release(c2)
                await pool.close_all()

        asyncio.run(run())

    def test_idle_ttl_evicts_connection(self):
        fake_conn, mock_cm = _fake_spawn_stack()
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=1.0)

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                c1 = await pool.acquire("hermes", "/tmp")
                await pool.release(c1)
                # Simulate the connection being idle past the TTL
                c1.last_used -= 5.0
                c2 = await pool.acquire("hermes", "/tmp")
                assert c1 is not c2
                assert mock_cm.__aenter__.await_count == 2
                await pool.release(c2)
                await pool.close_all()

        asyncio.run(run())

    def test_close_all_destroys_connections(self):
        fake_conn, mock_cm = _fake_spawn_stack()
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=60)

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                c = await pool.acquire("hermes", "/tmp")
                await pool.release(c)
                await pool.close_all()
                assert pool.stats()["connections"] == 0
                assert mock_cm.__aexit__.await_count == 1

        asyncio.run(run())


class TestPoolErrorHandling:
    """Error paths: initialize fail, prompt fail, cancel mid-stream."""

    def test_initialize_failure_leaves_no_pool_entry(self):
        """initialize fail → transport closed, no orphan pool entry."""
        fake_conn, mock_cm = _fake_spawn_stack()
        fake_conn.initialize = AsyncMock(side_effect=RuntimeError("boom"))
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=60)

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                with pytest.raises(LLMConnectionError):
                    await pool.acquire("hermes", "/tmp")
                assert pool.stats()["connections"] == 0
                assert mock_cm.__aexit__.await_count == 1

        asyncio.run(run())

    def test_prompt_failure_discards_connection(self):
        """new_session fail → conn destroyed (discard) + transport closed."""
        fake_conn, mock_cm = _fake_spawn_stack()
        fake_conn.new_session = AsyncMock(side_effect=RuntimeError("session boom"))
        backend = HermesACPBackend(
            ModelConfig(url="", model="hermes", timeout=30, backend="hermes_acp")
        )

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                with pytest.raises(LLMConnectionError):
                    async for _ in backend._run_acp_pooled("test", "/tmp"):
                        pass
                pool = get_acp_pool()
                assert pool.stats()["connections"] == 0
                assert mock_cm.__aexit__.await_count == 1

        asyncio.run(run())

    def test_cancel_mid_stream_discards_connection(self):
        """Client cancel mid-stream → conn NOT recycled (discard)."""
        fake_conn, mock_cm = _fake_spawn_stack()
        backend = HermesACPBackend(
            ModelConfig(url="", model="hermes", timeout=30, backend="hermes_acp")
        )

        async def fake_prompt_on_connection(pooled, prompt):
            yield "hello"
            await asyncio.Event().wait()  # never completes

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ), patch.object(
                backend, "_prompt_on_connection", fake_prompt_on_connection
            ):
                agen = backend._run_acp_pooled("test", "/tmp")
                got_first = asyncio.Event()

                async def drain():
                    async for _ in agen:
                        if not got_first.is_set():
                            got_first.set()

                task = asyncio.create_task(drain())
                await asyncio.wait_for(got_first.wait(), timeout=5)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                pool = get_acp_pool()
                assert pool.stats()["connections"] == 0
                assert mock_cm.__aexit__.await_count == 1

        asyncio.run(run())