"""Test utilities for Hermes MCP server — parsing and helper functions."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

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

    def test_parse_json_escaped_quote_keys(self):
        """Should normalize escaped-quote keys (e.g. {\"intent\": \"...\"})."""
        text = r'<|tool_call>call:execute_intent{"\"intent\"": "\"prendre une capture\""}<tool_call|>'
        result = parse_tool_call_tag(text)
        assert result is not None
        func_name, func_args = result
        assert func_name == "execute_intent"
        assert func_args == {"intent": "prendre une capture"}


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


class TestCallToolFileOperations:
    """Tests for call_tool read_file / write_file with mocked filesystem_service."""

    def _make_server(self):
        from backend.infrastructure.mcp.server import HermesMCPServer

        server = HermesMCPServer.__new__(HermesMCPServer)
        server.llm_client = None
        server.filesystem_service = MagicMock()
        return server

    def test_call_tool_read_file_success(self):
        server = self._make_server()
        file_content = MagicMock()
        file_content.content = "print('hello')"
        server.filesystem_service.read_file.return_value = file_content

        result = asyncio.run(server.call_tool("read_file", {"path": "main.py"}))
        assert result["content"] == "print('hello')"
        server.filesystem_service.read_file.assert_called_once_with("main.py")

    def test_call_tool_read_file_not_found(self):
        server = self._make_server()
        server.filesystem_service.read_file.return_value = None

        result = asyncio.run(server.call_tool("read_file", {"path": "missing.py"}))
        assert "non trouve" in result["content"]

    def test_call_tool_write_file_success(self):
        server = self._make_server()
        server.filesystem_service.write_file.return_value = True

        result = asyncio.run(server.call_tool(
            "write_file", {"path": "main.py", "content": "print('hi')"}
        ))
        assert "Succes" in result["content"]
        server.filesystem_service.write_file.assert_called_once_with("main.py", "print('hi')")

    def test_call_tool_write_file_failure(self):
        server = self._make_server()
        server.filesystem_service.write_file.return_value = False

        result = asyncio.run(server.call_tool(
            "write_file", {"path": "main.py", "content": "x"}
        ))
        assert "Echec" in result["content"]


class TestBuildTools:
    """Tests for _build_tools — OpenAI-compatible tools parameter."""

    def _make_server(self):
        from backend.infrastructure.mcp.server import HermesMCPServer

        server = HermesMCPServer.__new__(HermesMCPServer)
        server.llm_client = None
        return server

    def test_build_tools_excludes_chat(self):
        """chat tool should not be exposed to the LLM (avoids recursion)."""
        server = self._make_server()
        tools = server._build_tools()
        names = [t["function"]["name"] for t in tools]
        assert "chat" not in names
        assert "execute_intent" in names
        assert "read_file" in names
        assert "write_file" in names

    def test_build_tools_openai_shape(self):
        """Each tool should have OpenAI function shape with JSON schema params."""
        server = self._make_server()
        tools = server._build_tools()
        for t in tools:
            assert t["type"] == "function"
            assert "name" in t["function"]
            assert "description" in t["function"]
            assert t["function"]["parameters"]["type"] == "object"

    def test_build_tools_read_file_schema(self):
        """read_file schema should be carried into the tools parameter."""
        server = self._make_server()
        tools = server._build_tools()
        read_file = next(
            t for t in tools if t["function"]["name"] == "read_file"
        )
        params = read_file["function"]["parameters"]
        assert isinstance(params, dict)
        assert params["required"] == ["path"]
        properties = params.get("properties", {})
        assert isinstance(properties, dict)
        assert "path" in properties


class TestHandleChatNativeTools:
    """Tests for _handle_chat native tool calling loop."""

    def _make_server(self, llm_client):
        from backend.infrastructure.mcp.server import HermesMCPServer

        server = HermesMCPServer.__new__(HermesMCPServer)
        server.llm_client = llm_client
        server.llm_model = "test-model"
        server._sessions = {}
        server._active_streams = {}
        server._max_sessions = 100
        call_tool_mock = AsyncMock(
            return_value={"content": "tool executed"}
        )
        setattr(server, "call_tool", call_tool_mock)
        return server, call_tool_mock

    def _mock_response(self, message):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = message
        return resp

    def test_native_tool_call_executed(self):
        """Native tool_calls should execute the tool and return the follow-up."""
        from backend.infrastructure.mcp.server import HermesMCPServer

        llm = MagicMock()
        # Round 1: native tool call
        tc = MagicMock()
        tc.id = "call_1"
        tc.type = "function"
        tc.function.name = "read_file"
        tc.function.arguments = json.dumps({"path": "main.py"})
        msg1 = MagicMock()
        msg1.content = ""
        msg1.tool_calls = [tc]
        # Round 2: plain text answer
        msg2 = MagicMock()
        msg2.content = "Voici le fichier."
        msg2.tool_calls = None
        llm.chat.completions.create.side_effect = [
            self._mock_response(msg1),
            self._mock_response(msg2),
        ]

        server, call_tool_mock = self._make_server(llm)
        result = asyncio.run(server._handle_chat("lis main.py"))

        assert result["content"] == "Voici le fichier."
        call_tool_mock.assert_called_once_with("read_file", {"path": "main.py"})
        # tools= and tool_choice=auto must be passed
        kwargs = llm.chat.completions.create.call_args_list[0].kwargs
        assert kwargs["tool_choice"] == "auto"
        assert "tools" in kwargs
        # tool result must be fed back as role=tool message
        sent_messages = kwargs["messages"]
        tool_msgs = [m for m in sent_messages if m["role"] == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "call_1"

    def test_tag_fallback_still_works(self):
        """Models without native tools should still work via tag protocol."""
        llm = MagicMock()
        msg1 = MagicMock()
        msg1.content = '<|tool_call>call:read_file{"path": "a.py"}<tool_call|>'
        msg1.tool_calls = None
        msg2 = MagicMock()
        msg2.content = "Fait."
        msg2.tool_calls = None
        llm.chat.completions.create.side_effect = [
            self._mock_response(msg1),
            self._mock_response(msg2),
        ]

        server, call_tool_mock = self._make_server(llm)
        result = asyncio.run(server._handle_chat("lis a.py"))

        assert result["content"] == "Fait."
        call_tool_mock.assert_called_once_with("read_file", {"path": "a.py"})

    def test_loop_bounded_by_max_rounds(self):
        """A model that keeps calling tools must stop after MAX_TOOL_ROUNDS."""
        from backend.infrastructure.mcp.server import MAX_TOOL_ROUNDS

        llm = MagicMock()
        tc = MagicMock()
        tc.id = "call_x"
        tc.type = "function"
        tc.function.name = "read_file"
        tc.function.arguments = "{}"
        msg = MagicMock()
        msg.content = ""
        msg.tool_calls = [tc]
        llm.chat.completions.create.return_value = self._mock_response(msg)

        server, _ = self._make_server(llm)
        result = asyncio.run(server._handle_chat("boucle"))

        assert "exceeded max rounds" in result["content"]
        assert llm.chat.completions.create.call_count == MAX_TOOL_ROUNDS

    def test_timeout_aligned_with_settings(self):
        """LLM calls should use settings.llm_timeout as the request timeout."""
        from backend.domain.settings import settings

        llm = MagicMock()
        msg = MagicMock()
        msg.content = "réponse simple"
        msg.tool_calls = None
        llm.chat.completions.create.return_value = self._mock_response(msg)

        server, _ = self._make_server(llm)
        asyncio.run(server._handle_chat("bonjour"))

        kwargs = llm.chat.completions.create.call_args.kwargs
        assert kwargs["timeout"] == settings.llm_timeout


async def _collect(agen):
    """Collect all items from an async generator."""
    return [item async for item in agen]


class TestSessions:
    """Tests for Hermes session management and cancellation."""

    def _make_server(self, llm_client):
        from backend.infrastructure.mcp.server import HermesMCPServer

        server = HermesMCPServer.__new__(HermesMCPServer)
        server.llm_client = llm_client
        server.llm_model = "test-model"
        server._sessions = {}
        server._active_streams = {}
        server._max_sessions = 100
        return server

    def _mock_response(self, message):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = message
        return resp

    def test_handle_chat_creates_and_returns_session(self):
        """_handle_chat should create a session and return its id."""
        llm = MagicMock()
        msg = MagicMock()
        msg.content = "bonjour"
        msg.tool_calls = None
        llm.chat.completions.create.return_value = self._mock_response(msg)

        server = self._make_server(llm)
        result = asyncio.run(server._handle_chat("salut"))

        assert "session_id" in result
        sid = result["session_id"]
        assert sid in server._sessions
        assert len(server._sessions[sid]) == 2  # user + assistant

    def test_handle_chat_reuses_session_history(self):
        """A second call with the same session_id should see prior messages."""
        llm = MagicMock()
        msg = MagicMock()
        msg.content = "première réponse"
        msg.tool_calls = None
        llm.chat.completions.create.return_value = self._mock_response(msg)

        server = self._make_server(llm)
        sid = asyncio.run(server._handle_chat("bonjour"))["session_id"]
        asyncio.run(server._handle_chat("encore", sid))

        sent = llm.chat.completions.create.call_args_list[1].kwargs["messages"]
        roles = [m["role"] for m in sent]
        assert roles.count("user") == 2
        assert sent[1]["content"] == "bonjour"
        assert sent[3]["content"] == "encore"

    def test_handle_chat_generates_new_session_when_none(self):
        """Calls without a session_id should get distinct sessions."""
        llm = MagicMock()
        msg = MagicMock()
        msg.content = "ok"
        msg.tool_calls = None
        llm.chat.completions.create.return_value = self._mock_response(msg)

        server = self._make_server(llm)
        sid1 = asyncio.run(server._handle_chat("a"))["session_id"]
        sid2 = asyncio.run(server._handle_chat("b"))["session_id"]

        assert sid1 != sid2
        assert len(server._sessions) == 2

    def test_session_cap_evicts_oldest(self):
        """When at capacity the oldest session should be evicted."""
        llm = MagicMock()
        msg = MagicMock()
        msg.content = "ok"
        msg.tool_calls = None
        llm.chat.completions.create.return_value = self._mock_response(msg)

        server = self._make_server(llm)
        server._max_sessions = 2
        sid1 = asyncio.run(server._handle_chat("a"))["session_id"]
        sid2 = asyncio.run(server._handle_chat("b"))["session_id"]
        sid3 = asyncio.run(server._handle_chat("c"))["session_id"]

        assert len(server._sessions) == 2
        assert sid1 not in server._sessions
        assert sid3 in server._sessions

    def test_cancel_active_stream(self):
        """cancel() should flag an active stream and return True."""
        server = self._make_server(None)
        server._active_streams["s1"] = False

        assert server.cancel("s1") is True
        assert server._active_streams["s1"] is True

    def test_cancel_inactive_stream(self):
        """cancel() should return False when no stream is active."""
        server = self._make_server(None)
        assert server.cancel("nope") is False

    def test_stream_chat_stops_on_cancel(self):
        """stream_chat should stop early when the session is cancelled."""
        llm = MagicMock()
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "hello"
        chunk.choices[0].delta.tool_calls = None
        llm.chat.completions.create.return_value = iter([chunk, chunk, chunk])

        server = self._make_server(llm)
        server._active_streams["s1"] = True

        collected = asyncio.run(_collect(server.stream_chat("hi", "s1")))

        assert collected == ["\n\n[cancelled]\n\n"]
        assert "s1" not in server._active_streams

    def test_stream_chat_persists_history(self):
        """stream_chat should store the conversation in the session."""
        llm = MagicMock()
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "réponse"
        chunk.choices[0].delta.tool_calls = None
        llm.chat.completions.create.return_value = iter([chunk])

        server = self._make_server(llm)
        asyncio.run(_collect(server.stream_chat("bonjour", "s1")))

        assert "s1" in server._sessions
        history = server._sessions["s1"]
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "bonjour"
        assert "s1" not in server._active_streams

    def test_clear_session(self):
        """clear_session should remove history and active-stream flag."""
        server = self._make_server(None)
        server._sessions["s1"] = [{"role": "user", "content": "hi"}]
        server._active_streams["s1"] = False

        assert server.clear_session("s1") is True
        assert "s1" not in server._sessions
        assert "s1" not in server._active_streams
        assert server.clear_session("s1") is False

    def test_list_sessions(self):
        """list_sessions should report session ids and message counts."""
        server = self._make_server(None)
        server._sessions["s1"] = [{"role": "user", "content": "a"}]
        server._sessions["s2"] = []

        sessions = server.list_sessions()
        by_id = {s["session_id"]: s for s in sessions}

        assert by_id["s1"]["message_count"] == 1
        assert by_id["s2"]["message_count"] == 0
