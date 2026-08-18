"""Tests for the LangGraph bridge to Hermes ACP (Phase 5)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def hermes_bridge():
    """Import the hermes_bridge module fresh."""
    from backend.domain.core.langgraph import hermes_bridge

    return hermes_bridge


# ── Tool definitions ─────────────────────────────────────────────────


class TestToolDefinitions:
    def test_get_hermes_tools_returns_list(self, hermes_bridge):
        """get_hermes_tools should return a non-empty list of tool dicts."""
        tools = hermes_bridge.get_hermes_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 4

    def test_get_hermes_tools_has_required_fields(self, hermes_bridge):
        """Each tool definition must have name, description, and parameters."""
        tools = hermes_bridge.get_hermes_tools()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert isinstance(tool["parameters"], dict)
            assert "type" in tool["parameters"]
            assert tool["parameters"]["type"] == "object"

    def test_get_hermes_tool_names(self, hermes_bridge):
        """get_hermes_tool_names should return the list of tool names."""
        names = hermes_bridge.get_hermes_tool_names()
        assert "hermes_read_file" in names
        assert "hermes_write_file" in names
        assert "hermes_execute_intent" in names
        assert "hermes_get_opencode_status" in names

    def test_read_file_has_path_param(self, hermes_bridge):
        """hermes_read_file should require a 'path' parameter."""
        tools = hermes_bridge.get_hermes_tools()
        read_tool = next(t for t in tools if t["name"] == "hermes_read_file")
        assert "path" in read_tool["parameters"]["properties"]
        assert "path" in read_tool["parameters"]["required"]

    def test_write_file_has_path_and_content(self, hermes_bridge):
        """hermes_write_file should require 'path' and 'content' parameters."""
        tools = hermes_bridge.get_hermes_tools()
        write_tool = next(t for t in tools if t["name"] == "hermes_write_file")
        props = write_tool["parameters"]["properties"]
        assert "path" in props
        assert "content" in props
        assert set(write_tool["parameters"]["required"]) == {"path", "content"}

    def test_execute_intent_has_intent_param(self, hermes_bridge):
        """hermes_execute_intent should require an 'intent' parameter."""
        tools = hermes_bridge.get_hermes_tools()
        intent_tool = next(t for t in tools if t["name"] == "hermes_execute_intent")
        assert "intent" in intent_tool["parameters"]["properties"]
        assert "intent" in intent_tool["parameters"]["required"]

    def test_get_opencode_status_has_no_required_params(self, hermes_bridge):
        """hermes_get_opencode_status should have no required parameters."""
        tools = hermes_bridge.get_hermes_tools()
        status_tool = next(
            t for t in tools if t["name"] == "hermes_get_opencode_status"
        )
        assert status_tool["parameters"]["required"] == []


# ── Prompt building ───────────────────────────────────────────────────


class TestBuildHermesPrompt:
    def test_read_file_prompt(self, hermes_bridge):
        """_build_hermes_prompt should produce the tool_call tag for read_file."""
        prompt = hermes_bridge._build_hermes_prompt(
            "hermes_read_file", {"path": "main.py"}
        )
        assert "call:read_file" in prompt
        assert '"path": "main.py"' in prompt
        assert "<|tool_call>" in prompt
        assert "<tool_call|>" in prompt

    def test_write_file_prompt(self, hermes_bridge):
        """_build_hermes_prompt should produce the tool_call tag for write_file."""
        prompt = hermes_bridge._build_hermes_prompt(
            "hermes_write_file", {"path": "test.py", "content": "print('hi')"}
        )
        assert "call:write_file" in prompt
        assert '"path": "test.py"' in prompt
        assert '"content": "print(\'hi\')"' in prompt

    def test_execute_intent_prompt(self, hermes_bridge):
        """_build_hermes_prompt should produce the tool_call tag for execute_intent."""
        prompt = hermes_bridge._build_hermes_prompt(
            "hermes_execute_intent", {"intent": "open VS Code"}
        )
        assert "call:execute_intent" in prompt
        assert '"intent": "open VS Code"' in prompt

    def test_get_opencode_status_prompt(self, hermes_bridge):
        """_build_hermes_prompt should produce the tool_call tag for get_opencode_status."""
        prompt = hermes_bridge._build_hermes_prompt("hermes_get_opencode_status", {})
        assert "call:get_opencode_status" in prompt


# ── call_hermes_tool ──────────────────────────────────────────────────


class TestCallHermesTool:
    def test_unknown_tool_raises_value_error(self, hermes_bridge):
        """call_hermes_tool should raise ValueError for unknown tool names."""
        with pytest.raises(ValueError, match="Unknown Hermes tool"):
            asyncio.run(hermes_bridge.call_hermes_tool("unknown_tool", {"foo": "bar"}))

    def test_call_read_file_success(self, hermes_bridge):
        """call_hermes_tool should invoke the backend and return the result."""
        mock_backend = MagicMock()

        async def fake_astream(prompt, **kwargs):
            yield "file content here"

        mock_backend.astream = fake_astream

        with patch.object(
            hermes_bridge, "_get_hermes_backend", return_value=mock_backend
        ):
            result = asyncio.run(
                hermes_bridge.call_hermes_tool("hermes_read_file", {"path": "main.py"})
            )

        assert result == "file content here"

    def test_call_write_file_success(self, hermes_bridge):
        """call_hermes_tool should work for write_file."""
        mock_backend = MagicMock()

        async def fake_astream(prompt, **kwargs):
            yield "Succes"

        mock_backend.astream = fake_astream

        with patch.object(
            hermes_bridge, "_get_hermes_backend", return_value=mock_backend
        ):
            result = asyncio.run(
                hermes_bridge.call_hermes_tool(
                    "hermes_write_file",
                    {"path": "test.py", "content": "print('hi')"},
                )
            )

        assert result == "Succes"

    def test_call_tool_propagates_errors(self, hermes_bridge):
        """call_hermes_tool should propagate exceptions from the backend."""
        mock_backend = MagicMock()

        async def fake_astream(prompt, **kwargs):
            yield  # make it an async generator
            raise RuntimeError("subprocess died")

        mock_backend.astream = fake_astream

        with patch.object(
            hermes_bridge, "_get_hermes_backend", return_value=mock_backend
        ):
            with pytest.raises(RuntimeError, match="subprocess died"):
                asyncio.run(
                    hermes_bridge.call_hermes_tool(
                        "hermes_read_file", {"path": "main.py"}
                    )
                )

    def test_call_tool_propagates_cancellation(self, hermes_bridge):
        """Cancellation must propagate and emit a failure event."""
        mock_backend = MagicMock()

        async def fake_astream(prompt, **kwargs):
            yield  # make it an async generator
            raise asyncio.CancelledError()

        mock_backend.astream = fake_astream

        with patch.object(
            hermes_bridge, "_get_hermes_backend", return_value=mock_backend
        ), patch.object(hermes_bridge, "emit_tool") as mock_emit:
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(
                    hermes_bridge.call_hermes_tool(
                        "hermes_read_file", {"path": "main.py"}
                    )
                )
            # A failure event is emitted so the Debug panel does not
            # show a dangling success for the cancelled call.
            mock_emit.assert_any_call(
                "hermes_read_file", {"path": "main.py"}, "cancelled", success=False
            )

# ── Provider helpers ──────────────────────────────────────────────────


class TestProviderHelpers:
    def test_is_hermes_provider_hermes(self, hermes_bridge):
        """is_hermes_provider should return True for 'hermes'."""
        assert hermes_bridge.is_hermes_provider("hermes") is True

    def test_is_hermes_provider_hermes_acp(self, hermes_bridge):
        """is_hermes_provider should return True for 'hermes_acp'."""
        assert hermes_bridge.is_hermes_provider("hermes_acp") is True

    def test_is_hermes_provider_ollama(self, hermes_bridge):
        """is_hermes_provider should return False for 'ollama'."""
        assert hermes_bridge.is_hermes_provider("ollama") is False

    def test_is_hermes_provider_case_insensitive(self, hermes_bridge):
        """is_hermes_provider should be case-insensitive."""
        assert hermes_bridge.is_hermes_provider("HERMES") is True
        assert hermes_bridge.is_hermes_provider("Hermes_ACP") is True

    def test_should_use_hermes_with_hermes_provider(self, hermes_bridge):
        """should_use_hermes should return True when provider is hermes_acp."""
        state = {
            "metadata": {"provider": "hermes_acp"},
        }
        assert hermes_bridge.should_use_hermes(state) is True

    def test_should_use_hermes_with_ollama_provider(self, hermes_bridge):
        """should_use_hermes should return False when provider is ollama."""
        state = {
            "metadata": {"provider": "ollama"},
        }
        assert hermes_bridge.should_use_hermes(state) is False

    def test_should_use_hermes_with_no_metadata(self, hermes_bridge):
        """should_use_hermes should return False when no metadata."""
        state = {}
        assert hermes_bridge.should_use_hermes(state) is False

    def test_should_use_hermes_with_task_type_routing(self, hermes_bridge):
        """should_use_hermes should return True when task_type matches setting."""
        with patch.object(
            hermes_bridge.settings, "hermes_acp_provider", "code,reasoning"
        ):
            state = {
                "task_type": json.dumps({"task_type": "code", "summary": "test"}),
            }
            assert hermes_bridge.should_use_hermes(state) is True

    def test_should_use_hermes_with_non_matching_task_type(self, hermes_bridge):
        """should_use_hermes should return False when task_type doesn't match."""
        with patch.object(hermes_bridge.settings, "hermes_acp_provider", "code"):
            state = {
                "task_type": json.dumps({"task_type": "general", "summary": "test"}),
            }
            assert hermes_bridge.should_use_hermes(state) is False


# ── hermes_execute_node ───────────────────────────────────────────────


class TestHermesExecuteNode:
    def test_success_returns_result(self, hermes_bridge):
        """hermes_execute_node should return the tool result on success."""
        state = {"steps_history": []}

        with patch.object(
            hermes_bridge, "call_hermes_tool", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = "file content"

            result = asyncio.run(
                hermes_bridge.hermes_execute_node(
                    state, "hermes_read_file", {"path": "main.py"}
                )
            )

        assert result["hermes_tool_result"]["success"] is True
        assert result["hermes_tool_result"]["result"] == "file content"
        assert result["hermes_tool_result"]["tool"] == "hermes_read_file"

    def test_failure_returns_error(self, hermes_bridge):
        """hermes_execute_node should return error info on failure."""
        state = {"steps_history": []}

        with patch.object(
            hermes_bridge, "call_hermes_tool", new_callable=AsyncMock
        ) as mock_call:
            mock_call.side_effect = RuntimeError("connection refused")

            result = asyncio.run(
                hermes_bridge.hermes_execute_node(
                    state, "hermes_read_file", {"path": "main.py"}
                )
            )

        assert result["hermes_tool_result"]["success"] is False
        assert "connection refused" in result["hermes_tool_result"]["result"]
