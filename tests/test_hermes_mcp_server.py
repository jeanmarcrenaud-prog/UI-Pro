"""Test utilities for Hermes MCP server — parsing and helper functions."""
import json
import pytest

from backend.infrastructure.mcp.server import (
    parse_tool_call_tag,
    _parse_kv,
    build_followup_messages,
    get_server,
    _build_system_prompt,
 )


class TestParseToolCallTag:
    """Tests for the parse_tool_call_tag function."""

    def test_parse_json_brace_format(self):
        """Should parse <|tool_call>call:NAME{"json": "args"}<tool_call|> format."""
        text = '<|tool_call>call:execute_intent{"intent": "launch msedge.exe"}<tool_call|>'
        result = parse_tool_call_tag(text)
        assert result is not None
        func_name, func_args = result
        assert func_name == "execute_intent"
        assert func_args == {"intent": "launch msedge.exe"}

    def test_parse_json_brace_format_multiple_args(self):
        """Should parse multiple JSON arguments."""
        text = '<|tool_call>call:write_file{"path": "hello.py", "content": "print(1)"}<tool_call|>'
        result = parse_tool_call_tag(text)
        assert result is not None
        func_name, func_args = result
        assert func_name == "write_file"
        assert func_args == {"path": "hello.py", "content": "print(1)"}

    def test_parse_paren_format(self):
        """Should parse <|tool_call>call:NAME(key="value")<tool_call|> format."""
        text = '<|tool_call>call:read_file(path="hello.py")<tool_call|>'
        result = parse_tool_call_tag(text)
        assert result is not None
        func_name, func_args = result
        assert func_name == "read_file"
        assert func_args == {"path": "hello.py"}

    def test_parse_no_match(self):
        """Should return None when no tool call pattern is found."""
        text = "This is just a regular message with no tool call."
        result = parse_tool_call_tag(text)
        assert result is None

    def test_parse_empty_text(self):
        """Should return None for empty input."""
        result = parse_tool_call_tag("")
        assert result is None

    def test_parse_json_fallback_to_kv(self):
        """Should fall back to KV parsing when JSON parse fails."""
        text = '<|tool_call>call:execute_intent{intent: launch msedge}<tool_call|>'
        result = parse_tool_call_tag(text)
        assert result is not None
        func_name, func_args = result
        assert func_name == "execute_intent"
        assert func_args == {"intent": "launch msedge"}


class TestParseKV:
    """Tests for the _parse_kv helper function."""

    def test_parse_colon_separator(self):
        """Should parse key: value pairs."""
        result = _parse_kv("key1: val1, key2: val2", sep=":")
        assert result == {"key1": "val1", "key2": "val2"}

    def test_parse_equals_separator(self):
        """Should parse key=value pairs."""
        result = _parse_kv("key1=val1, key2=val2", sep="=")
        assert result == {"key1": "val1", "key2": "val2"}

    def test_parse_with_quotes(self):
        """Should strip quotes from values."""
        result = _parse_kv('key1: "val1", key2: \'val2\'', sep=":")
        assert result == {"key1": "val1", "key2": "val2"}

    def test_parse_empty_input(self):
        """Should return empty dict for empty input."""
        assert _parse_kv("", sep=":") == {}

    def test_parse_no_separator(self):
        """Should skip entries without separator."""
        result = _parse_kv("key1: val1, nodelimiter, key2: val2", sep=":")
        assert result == {"key1": "val1", "key2": "val2"}


class TestBuildFollowupMessages:
    """Tests for the build_followup_messages function."""

    def test_build_followup_with_dict_result(self):
        """Should build followup message from dict result."""
        result = {"content": "File created successfully"}
        messages = build_followup_messages(
            "original text", "write_file", {"path": "test.py"}, result
        )
        assert len(messages) == 1
        assert messages[0]["role"] == "system"
        assert "write_file" in messages[0]["content"]
        assert "File created successfully" in messages[0]["content"]

    def test_build_followup_with_non_dict_result(self):
        """Should convert non-dict result to string (no crash)."""
        result = "Some string result"
        messages = build_followup_messages(
            "original text", "execute_intent", {"intent": "test"}, result
        )
        assert len(messages) == 1
        assert "Some string result" in messages[0]["content"]
        """Should fall back to string representation when result lacks 'content'."""
        result = {"status": "unknown"}
        messages = build_followup_messages(
            "original text", "execute_intent", {"intent": "test"}, result
        )
        assert len(messages) == 1
        assert "unknown" in messages[0]["content"]

    def test_build_followup_contains_args(self):
        """Followup message should include the tool args."""
        result = {"content": "ok"}
        messages = build_followup_messages(
            "original text", "read_file", {"path": "hello.py"}, result
        )
        assert "read_file" in messages[0]["content"]
        assert "hello.py" in messages[0]["content"]


class TestBuildSystemPrompt:
    """Tests for the _build_system_prompt helper."""

    def test_prompt_contains_base_text(self):
        """Should include the base identity text."""

        prompt = _build_system_prompt(["read_file"])
        assert "Hermes, the intelligence engine" in prompt
        assert "run locally" in prompt

    def test_prompt_includes_tool_names(self):
        """Should list available tools."""
        prompt = _build_system_prompt(["read_file", "write_file"])
        assert "read_file" in prompt
        assert "write_file" in prompt

    def test_prompt_excludes_chat_tool(self):
        """Chat tool should not appear in available tools list (excluded by caller)."""
        prompt = _build_system_prompt(["execute_intent"])
        assert "chat" not in prompt

class TestHermesMCPServerTools:
    """Tests for HermesMCPServer tool listing and resources."""

    def test_list_tools_contains_all_expected(self):
        """Should list all expected tools."""
        from backend.infrastructure.mcp.server import HermesMCPServer

        # We can test list_tools without __init__ by calling it directly
        # on a partially constructed object
        server = HermesMCPServer.__new__(HermesMCPServer)
        tools = server.list_tools()

        tool_names = [t["name"] for t in tools]
        assert "execute_intent" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "chat" in tool_names
        assert "get_opencode_status" in tool_names

    def test_list_tools_read_file_schema(self):
        """read_file tool should have path as required arg."""
        from backend.infrastructure.mcp.server import HermesMCPServer

        server = HermesMCPServer.__new__(HermesMCPServer)
        tools = server.list_tools()

        read_file_tool = next(t for t in tools if t["name"] == "read_file")
        assert read_file_tool["input_schema"]["required"] == ["path"]
        assert "path" in read_file_tool["input_schema"]["properties"]

    def test_list_tools_write_file_schema(self):
        """write_file tool should have path and content as required args."""
        from backend.infrastructure.mcp.server import HermesMCPServer

        server = HermesMCPServer.__new__(HermesMCPServer)
        tools = server.list_tools()

        write_file_tool = next(t for t in tools if t["name"] == "write_file")
        assert "path" in write_file_tool["input_schema"]["required"]
        assert "content" in write_file_tool["input_schema"]["required"]

    def test_list_resources_contains_editor_state(self):
        """Should list hermes://editor_state resource."""
        from backend.infrastructure.mcp.server import HermesMCPServer

        server = HermesMCPServer.__new__(HermesMCPServer)
        resources = server.list_resources()

        uris = [r["uri"] for r in resources]
        assert "hermes://editor_state" in uris
        assert "hermes://project_context" in uris


class TestGetServer:
    """Tests for the get_server() lazy initialization function."""

    def test_get_server_singleton(self):
        """get_server should return the same instance on repeated calls."""
        from backend.infrastructure.mcp.server import get_server

        # Reset the singleton for this test
        import backend.infrastructure.mcp.server as server_module
        original = server_module._server_instance
        server_module._server_instance = None

        try:
            instance1 = get_server()
            instance2 = get_server()
            assert instance1 is instance2
        finally:
            server_module._server_instance = original

    def test_get_server_creates_instance(self):
        """get_server should create an instance when none exists."""
        import backend.infrastructure.mcp.server as server_module

        original = server_module._server_instance
        server_module._server_instance = None

        try:
            server = get_server()
            assert server is not None
            assert hasattr(server, "list_tools")
            assert hasattr(server, "call_tool")
            assert hasattr(server, "stream_chat")
        finally:
            server_module._server_instance = original


class TestCallTool:
    """Tests for HermesMCPServer.call_tool with mocked dependencies."""

    def _make_server(self):
        """Create a HermesMCPServer without running __init__."""
        from backend.infrastructure.mcp.server import HermesMCPServer

        server = HermesMCPServer.__new__(HermesMCPServer)
        server.llm_client = None
        return server

    def test_call_tool_unknown_tool(self):
        """Should return error for unknown tool."""
        server = self._make_server()
        result = server.__dict__
        # call_tool is async, need to run it
        import asyncio

        result = asyncio.run(server.call_tool("nonexistent_tool", {}))
        assert "Erreur" in result["content"]
        assert "nonexistent_tool" in result["content"]

    def test_call_tool_not_found_message(self):
        """Error message should include the tool name."""
        server = self._make_server()
        import asyncio

        result = asyncio.run(server.call_tool("unknown_tool", {"arg": "val"}))
        assert "unknown_tool" in result["content"]
