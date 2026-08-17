"""Tests for Hermes ACP connection pool."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.infrastructure.llm.hermes_acp import (
    HermesACPConnectionPool,
    reset_acp_pool_for_tests,
)


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

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(
        return_value=(MagicMock(), MagicMock(), MagicMock())
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