"""Tests for the HermesACPBackend (Phase 4 direct ACP transport)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.infrastructure.llm.errors import LLMConnectionError
from backend.infrastructure.llm.factory import list_available_backends
from backend.infrastructure.llm.models import ModelConfig


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def acp_backend():
    """Create a HermesACPBackend with a dummy command."""
    from backend.infrastructure.llm.hermes_acp import HermesACPBackend

    config = ModelConfig(url="", model="hermes", timeout=30, backend="hermes_acp")
    return HermesACPBackend(config)


# ── Registration ─────────────────────────────────────────────────────


class TestBackendRegistration:
    def test_hermes_acp_in_available_backends(self):
        """The hermes_acp backend should be registered by the factory."""
        backends = list_available_backends()
        assert "hermes_acp" in backends

    def test_get_backend_returns_hermes_acp(self):
        """get_backend should return a HermesACPBackend instance."""
        from backend.infrastructure.llm.factory import get_backend
        from backend.infrastructure.llm.hermes_acp import HermesACPBackend

        backend = get_backend("hermes_acp")
        assert isinstance(backend, HermesACPBackend)
        assert backend.backend_name == "hermes_acp"


# ── Command resolution ───────────────────────────────────────────────


class TestCommandResolution:
    def test_default_command_is_hermes(self, acp_backend):
        """When config.url is empty, the command should default to 'hermes'."""
        assert acp_backend._command == "hermes"

    def test_config_url_overrides_command(self):
        """When config.url is set, it should be used as the command."""
        from backend.infrastructure.llm.hermes_acp import HermesACPBackend

        config = ModelConfig(url="/custom/path/hermes", model="hermes", backend="hermes_acp")
        backend = HermesACPBackend(config)
        assert backend._command == "/custom/path/hermes"


# ── list_models ──────────────────────────────────────────────────────


class TestListModels:
    def test_list_models_returns_hermes(self, acp_backend):
        """list_models should return a single 'hermes' entry."""
        models = acp_backend.list_models()
        assert len(models) == 1
        assert models[0]["name"] == "hermes"
        assert models[0]["available"] is True


# ── astream ──────────────────────────────────────────────────────────


class TestAstream:
    def test_astream_yields_text_deltas(self, acp_backend):
        """astream should yield text chunks from AgentMessageChunk updates."""
        from acp.schema import AgentMessageChunk, TextContentBlock

        # Build a fake connection that simulates the ACP lifecycle
        fake_conn = MagicMock()
        fake_conn.initialize = AsyncMock()
        fake_conn.new_session = AsyncMock(
            return_value=MagicMock(session_id="sess_123")
        )
        fake_conn.prompt = AsyncMock(return_value=MagicMock())
        fake_conn.close_session = AsyncMock()
        fake_conn.close = AsyncMock()

        # The client's session_update will be called by the connection's
        # receive loop. We simulate this by having the prompt task
        # trigger session_update calls.
        async def fake_prompt(prompt, session_id, message_id=None, **kwargs):
            # Simulate the agent sending text chunks via session_update
            client = acp_backend._last_client  # set by _run_acp
            await client.session_update(
                session_id,
                AgentMessageChunk(
                    content=TextContentBlock(type="text", text="Hello "),
                    session_update="agent_message_chunk",
                ),
            )
            await client.session_update(
                session_id,
                AgentMessageChunk(
                    content=TextContentBlock(type="text", text="World"),
                    session_update="agent_message_chunk",
                ),
            )
            return MagicMock()

        fake_conn.prompt = fake_prompt

        async def run_test():
            chunks = []
            async for chunk in acp_backend._run_acp("test prompt"):
                chunks.append(chunk)
            return chunks

        with patch(
            "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport"
        ) as mock_spawn, patch(
            "backend.infrastructure.llm.hermes_acp.connect_to_agent",
            return_value=fake_conn,
        ) as mock_conn:  # noqa: F841 - connect_to_agent is patched
            # spawn_stdio_transport is an async context manager
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(
                return_value=(MagicMock(), MagicMock(), MagicMock())
            )
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            chunks = asyncio.run(run_test())

        assert chunks == ["Hello ", "World"]
        fake_conn.initialize.assert_awaited_once()
        fake_conn.new_session.assert_awaited_once()
        fake_conn.close_session.assert_awaited_once_with("sess_123")

    def test_astream_propagates_prompt_errors(self, acp_backend):
        """astream should propagate exceptions from the prompt task."""
        from acp.exceptions import RequestError

        fake_conn = MagicMock()
        fake_conn.initialize = AsyncMock()
        fake_conn.new_session = AsyncMock(
            return_value=MagicMock(session_id="sess_123")
        )
        fake_conn.prompt = AsyncMock(
            side_effect=RequestError(-32603, "Agent crashed")
        )
        fake_conn.close_session = AsyncMock()
        fake_conn.close = AsyncMock()

        async def run_test():
            async for _ in acp_backend._run_acp("test prompt"):
                pass

        with patch(
            "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport"
        ) as mock_spawn, patch(
            "backend.infrastructure.llm.hermes_acp.connect_to_agent",
            return_value=fake_conn,
        ):
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(
                return_value=(MagicMock(), MagicMock(), MagicMock())
            )
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            with pytest.raises(RequestError):
                asyncio.run(run_test())


# ── generate (sync) ──────────────────────────────────────────────────


class TestGenerate:
    def test_generate_returns_full_response(self, acp_backend):
        """generate should collect all chunks into a single string."""
        with patch.object(acp_backend, "_generate_async", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "Hello World"
            result = acp_backend.generate("test")
            assert result == "Hello World"
            mock_gen.assert_awaited_once()

    def test_generate_wraps_connection_error(self, acp_backend):
        """generate should wrap non-LLMBackendError exceptions."""
        with patch.object(acp_backend, "_generate_async", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = RuntimeError("subprocess died")
            with pytest.raises(LLMConnectionError):
                acp_backend.generate("test")


# ── stream (sync) ────────────────────────────────────────────────────


class TestStream:
    def test_stream_yields_chunks(self, acp_backend):
        """stream should yield chunks synchronously."""
        async def fake_async_gen():
            yield "Hello"
            yield " World"

        with patch.object(acp_backend, "_run_acp", return_value=fake_async_gen()):
            chunks = list(acp_backend.stream("test"))
            assert chunks == ["Hello", " World"]


# ── health_check ─────────────────────────────────────────────────────


class TestHealthCheck:
    def test_health_check_ok(self, acp_backend):
        """health_check should return ok status with latency."""
        from acp.schema import Implementation

        fake_conn = MagicMock()
        fake_conn.initialize = AsyncMock(
            return_value=MagicMock(
                agent_info=Implementation(name="hermes", title="Hermes", version="1.0.0")
            )
        )
        fake_conn.close = AsyncMock()

        with patch(
            "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport"
        ) as mock_spawn, patch(
            "backend.infrastructure.llm.hermes_acp.connect_to_agent",
            return_value=fake_conn,
        ):
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(
                return_value=(MagicMock(), MagicMock(), MagicMock())
            )
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            result = acp_backend.health_check()

        assert result["status"] == "ok"
        assert result["latency_ms"] >= 0
        assert result["agent_name"] == "hermes"
        assert result["agent_version"] == "1.0.0"
        assert result["error"] is None

    def test_health_check_error(self, acp_backend):
        """health_check should return error status on failure."""
        with patch(
            "backend.infrastructure.llm.hermes_acp.spawn_stdio_transport"
        ) as mock_spawn:
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("spawn failed"))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_spawn.return_value = mock_cm

            result = acp_backend.health_check()

        assert result["status"] == "error"
        assert result["error"] is not None
        assert "spawn failed" in result["error"]


# ── Client protocol ──────────────────────────────────────────────────


class TestHermesACPClient:
    def test_request_permission_auto_approves_first_option(self):
        """request_permission should auto-approve the first option."""
        from acp.schema import PermissionOption

        from backend.infrastructure.llm.hermes_acp import _HermesACPClient

        client = _HermesACPClient()
        options = [
            PermissionOption(name="Allow", option_id="opt_1", kind="allow_once"),
            PermissionOption(name="Allow all", option_id="opt_2", kind="allow_always"),
        ]

        async def run_test():
            return await client.request_permission(options, "sess_1", MagicMock())

        result = asyncio.run(run_test())
        assert result.outcome.outcome == "selected"
        assert result.outcome.option_id == "opt_1"

    def test_session_update_extracts_text(self):
        """session_update should extract text from AgentMessageChunk."""
        from acp.schema import AgentMessageChunk, TextContentBlock

        from backend.infrastructure.llm.hermes_acp import _HermesACPClient

        client = _HermesACPClient()

        async def run_test():
            await client.session_update(
                "sess_1",
                AgentMessageChunk(
                    content=TextContentBlock(type="text", text="Hello"),
                    session_update="agent_message_chunk",
                ),
            )
            return client._queue.get_nowait()

        text = asyncio.run(run_test())
        assert text == "Hello"

    def test_session_update_ignores_non_text(self):
        """session_update should ignore non-AgentMessageChunk updates."""
        from acp.schema import AgentThoughtChunk, TextContentBlock

        from backend.infrastructure.llm.hermes_acp import _HermesACPClient

        client = _HermesACPClient()

        async def run_test():
            await client.session_update(
                "sess_1",
                AgentThoughtChunk(
                    content=TextContentBlock(type="text", text="thinking"),
                    session_update="agent_thought_chunk",
                ),
            )
            # Queue should be empty
            assert client._queue.empty()

        asyncio.run(run_test())

    def test_fs_methods_raise_request_error(self):
        """File-system methods should raise RequestError."""
        from acp.exceptions import RequestError

        from backend.infrastructure.llm.hermes_acp import _HermesACPClient

        client = _HermesACPClient()

        async def run_test():
            with pytest.raises(RequestError):
                await client.write_text_file("content", "/path", "sess_1")
            with pytest.raises(RequestError):
                await client.read_text_file("/path", "sess_1")

        asyncio.run(run_test())

    def test_terminal_methods_raise_request_error(self):
        """Terminal methods should raise RequestError."""
        from acp.exceptions import RequestError

        from backend.infrastructure.llm.hermes_acp import _HermesACPClient

        client = _HermesACPClient()

        async def run_test():
            with pytest.raises(RequestError):
                await client.create_terminal("ls", "sess_1")
            with pytest.raises(RequestError):
                await client.terminal_output("sess_1", "term_1")
            with pytest.raises(RequestError):
                await client.kill_terminal("sess_1", "term_1")

        asyncio.run(run_test())
