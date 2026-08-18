"""Tests for Hermes ACP connection pool."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.infrastructure.llm.errors import LLMBackendError, LLMConnectionError
from backend.infrastructure.llm.hermes_acp import (
    HermesACPBackend,
    HermesACPConnectionPool,
    _PooledConnection,
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


class TestPoolConcurrency:
    """Spawn must not hold the pool lock; closed pool rejects in-flight spawns."""

    @staticmethod
    def _fake_pooled(command, cwd):
        process = MagicMock()
        process.returncode = None  # subprocess still running
        return _PooledConnection(
            command=command,
            cwd=cwd,
            client=MagicMock(),
            conn=MagicMock(),
            transport_cm=MagicMock(),
            process=process,
        )

    def test_spawn_does_not_block_other_acquires(self):
        """A slow spawn must not hold the pool lock (latency contention)."""
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=60)

        async def run():
            spawn_started = asyncio.Event()
            release_spawn = asyncio.Event()

            async def slow_spawn(command, cwd):
                if command == "hermes":
                    spawn_started.set()
                    await release_spawn.wait()
                return self._fake_pooled(command, cwd)

            with patch.object(pool, "_spawn", slow_spawn):
                task1 = asyncio.create_task(pool.acquire("hermes", "/tmp"))
                await spawn_started.wait()  # task1 mid-spawn, lock released
                task2 = asyncio.create_task(pool.acquire("other", "/tmp"))
                done, pending = await asyncio.wait({task2}, timeout=1)
                assert task2 in done  # completed while task1 still spawning
                for t in pending:
                    t.cancel()
                release_spawn.set()
                c1 = await task1
                c2 = task2.result()
                await pool.release(c1)
                await pool.release(c2)
                await pool.close_all()

        asyncio.run(run())

    def test_acquire_after_close_destroys_spawned_conn(self):
        """An in-flight spawn after close_all is destroyed, not leaked."""
        fake_conn, mock_cm = _fake_spawn_stack()
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=60)

        async def run():
            spawn_started = asyncio.Event()
            release_spawn = asyncio.Event()
            original_spawn = pool._spawn

            async def slow_spawn(command, cwd):
                spawn_started.set()
                await release_spawn.wait()
                return await original_spawn(command, cwd)

            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ), patch.object(pool, "_spawn", slow_spawn):
                task = asyncio.create_task(pool.acquire("hermes", "/tmp"))
                await spawn_started.wait()
                await pool.close_all()  # close while spawn in flight
                release_spawn.set()
                with pytest.raises(LLMBackendError):
                    await task
                assert pool.stats()["connections"] == 0
                assert mock_cm.__aexit__.await_count == 1

        asyncio.run(run())


class TestPoolDynamicSettings:
    """max_size / idle_ttl follow runtime settings changes."""

    def test_settings_provider_reads_live_values(self):
        """Live values are read from the provider, not the static ones."""

        class FakeSettings:
            hermes_acp_pool_size = 5
            hermes_acp_pool_idle_ttl = 30.0

        pool = HermesACPConnectionPool(
            max_size=2, idle_ttl=120.0, settings_provider=lambda: FakeSettings()
        )
        assert pool._current_max_size() == 5
        assert pool._current_idle_ttl() == 30.0
        assert pool.stats()["max_size"] == 5
        assert pool.stats()["idle_ttl"] == 30.0

        # Runtime change is picked up on the next read.
        FakeSettings.hermes_acp_pool_size = 8
        FakeSettings.hermes_acp_pool_idle_ttl = 60.0
        assert pool._current_max_size() == 8
        assert pool.stats()["idle_ttl"] == 60.0

    def test_capacity_uses_live_max_size(self):
        """The capacity eviction respects the live max_size from settings."""
        fake_conn, mock_cm = _fake_spawn_stack()

        class FakeSettings:
            hermes_acp_pool_size = 1
            hermes_acp_pool_idle_ttl = 120.0

        pool = HermesACPConnectionPool(
            max_size=4, idle_ttl=120.0, settings_provider=lambda: FakeSettings()
        )

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
                c1.healthy = False  # not reusable
                c2 = await pool.acquire("hermes", "/tmp")
                assert c1 is not c2
                # Live max_size=1 → c1 evicted by the capacity branch.
                assert mock_cm.__aexit__.await_count == 1
                await pool.release(c2)
                await pool.close_all()

        asyncio.run(run())

    def test_idle_ttl_uses_live_value(self):
        """Eviction respects the live idle_ttl from settings."""
        fake_conn, mock_cm = _fake_spawn_stack()

        class FakeSettings:
            hermes_acp_pool_size = 4
            hermes_acp_pool_idle_ttl = 1.0

        pool = HermesACPConnectionPool(
            max_size=4, idle_ttl=120.0, settings_provider=lambda: FakeSettings()
        )

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
                c1.last_used -= 5.0  # idle past the live TTL
                c2 = await pool.acquire("hermes", "/tmp")
                assert c1 is not c2
                assert mock_cm.__aenter__.await_count == 2
                await pool.release(c2)
                await pool.close_all()

        asyncio.run(run())


class TestPoolMetrics:
    """P0: single connect_to_agent; P2: hit/miss/discard + latency metrics."""

    def test_spawn_calls_connect_to_agent_once(self):
        """_spawn must create exactly one ACP connection (P0 regression)."""
        fake_conn, mock_cm = _fake_spawn_stack()
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=60)

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ) as mock_connect:
                conn = await pool._spawn("hermes", "/tmp")
                assert mock_connect.call_count == 1
                assert conn.conn is fake_conn
                await pool.close_all()

        asyncio.run(run())

    def test_stats_tracks_hit_miss_discard_metrics(self):
        """hits/misses/discards and latency averages are populated."""
        fake_conn, mock_cm = _fake_spawn_stack()

        async def slow_initialize(*args, **kwargs):
            await asyncio.sleep(0.01)

        fake_conn.initialize = AsyncMock(side_effect=slow_initialize)
        pool = HermesACPConnectionPool(max_size=2, idle_ttl=60)

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                s = pool.stats()
                assert s["hits"] == 0
                assert s["misses"] == 0
                assert s["discards"] == 0
                assert s["spawn_ms_avg"] == 0.0
                assert s["acquire_wait_ms_avg"] == 0.0

                c1 = await pool.acquire("hermes", "/tmp")  # miss
                s = pool.stats()
                assert s["misses"] == 1
                assert s["hits"] == 0
                assert s["spawn_ms_avg"] > 0.0
                assert s["acquire_wait_ms_avg"] >= 0.0

                await pool.release(c1)
                c2 = await pool.acquire("hermes", "/tmp")  # hit
                assert c1 is c2
                s = pool.stats()
                assert s["hits"] == 1
                assert s["misses"] == 1

                await pool.release(c2, discard=True)  # discard
                s = pool.stats()
                assert s["discards"] == 1
                assert s["connections"] == 0
                await pool.close_all()

        asyncio.run(run())


class TestPoolTimeouts:
    """P0: operation timeout (prompt) + handshake timeout (spawn)."""

    def test_prompt_timeout_discards_connection(self):
        """A prompt that never finishes → timeout → conn discarded."""
        fake_conn, mock_cm = _fake_spawn_stack()
        backend = HermesACPBackend(
            ModelConfig(url="", model="hermes", timeout=2, backend="hermes_acp")
        )

        async def hang_prompt_on_connection(pooled, prompt):
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
                backend, "_prompt_on_connection", hang_prompt_on_connection
            ):
                with pytest.raises(
                    LLMConnectionError, match="timed out after 2.0s"
                ):
                    async for _ in backend._run_acp_pooled("test", "/tmp"):
                        pass
                pool = get_acp_pool()
                assert pool.stats()["connections"] == 0
                assert mock_cm.__aexit__.await_count == 1

        asyncio.run(run())

    def test_handshake_timeout_leaves_no_pool_entry(self):
        """Slow initialize → handshake timeout → no pool entry."""
        fake_conn, mock_cm = _fake_spawn_stack()

        async def slow_initialize(*args, **kwargs):
            await asyncio.sleep(5)

        fake_conn.initialize = AsyncMock(side_effect=slow_initialize)

        class FakeSettings:
            hermes_acp_handshake_timeout = 0.1  # clamped to 1.0s

        pool = HermesACPConnectionPool(
            max_size=2, idle_ttl=60, settings_provider=lambda: FakeSettings()
        )

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                with pytest.raises(
                    LLMConnectionError, match="handshake timed out"
                ):
                    await pool.acquire("hermes", "/tmp")
                assert pool.stats()["connections"] == 0
                assert mock_cm.__aexit__.await_count == 1

        asyncio.run(run())

    def test_hit_path_under_large_timeout(self):
        """Normal pooled prompt under a large timeout → reuse works."""
        fake_conn, mock_cm = _fake_spawn_stack()
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
                chunks1 = [
                    c async for c in backend._run_acp_pooled("first", "/tmp")
                ]
                chunks2 = [
                    c async for c in backend._run_acp_pooled("second", "/tmp")
                ]
                assert mock_cm.__aenter__.await_count == 1  # reused
                pool = get_acp_pool()
                assert pool.stats()["connections"] == 1
                await pool.close_all()

        asyncio.run(run())

    def test_oneshot_prompt_timeout(self):
        """Oneshot path: a hung prompt → timeout → transport closed."""
        fake_conn, mock_cm = _fake_spawn_stack()

        async def hang(*a, **k):
            await asyncio.Event().wait()

        fake_conn.prompt = AsyncMock(side_effect=hang)
        backend = HermesACPBackend(
            ModelConfig(url="", model="hermes", timeout=2, backend="hermes_acp")
        )

        async def run():
            with patch(
                "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport",
                return_value=mock_cm,
            ), patch(
                "backend.infrastructure.llm.hermes_acp.connect_to_agent",
                return_value=fake_conn,
            ):
                with pytest.raises(
                    LLMConnectionError, match="timed out after 2.0s"
                ):
                    async for _ in backend._run_acp_oneshot("test", cwd="/tmp"):
                        pass
                assert mock_cm.__aexit__.await_count == 1

        asyncio.run(run())