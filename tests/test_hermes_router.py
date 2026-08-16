"""Tests for the Hermes API router endpoints."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.transport.routers.hermes import router, ConversationRequest


@pytest.fixture
def hermes_client():
    """Create a FastAPI test client with the Hermes router mounted."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestHermesStatus:
    """Tests for GET /api/hermes/status."""

    def test_status_returns_available_and_tools(self, hermes_client):
        """Status endpoint should return available=true and list of tools."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.list_tools.return_value = [
                {"name": "execute_intent", "description": "test"},
                {"name": "read_file", "description": "test"},
            ]
            mock_get_server.return_value = mock_server

            response = hermes_client.get("/api/hermes/status")

            assert response.status_code == 200
            data = response.json()
            assert data["available"] is True
            assert len(data["tools"]) == 2
            assert data["tools"][0]["name"] == "execute_intent"

    def test_status_calls_get_server_once(self, hermes_client):
        """Status endpoint should call get_server exactly once."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.list_tools.return_value = []
            mock_get_server.return_value = mock_server

            hermes_client.get("/api/hermes/status")

            mock_get_server.assert_called_once()


class TestHermesConversation:
    """Tests for POST /api/hermes/conversation."""

    def test_conversation_success(self, hermes_client):
        """Conversation endpoint should return response from chat tool."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.call_tool = AsyncMock(
                return_value={"content": "Hello from Hermes!"}
            )
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation",
                json={"message": "Hello"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Hello from Hermes!"
            mock_server.call_tool.assert_awaited_once_with(
                "chat", {"message": "Hello", "session_id": None}
            )

    def test_conversation_error_500(self, hermes_client):
        """Conversation endpoint should return 500 on tool failure."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.call_tool = AsyncMock(
                side_effect=Exception("LLM connection failed")
            )
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation",
                json={"message": "Hello"},
            )

            assert response.status_code == 500
            data = response.json()
            assert "LLM connection failed" in data["detail"]

    def test_conversation_empty_context(self, hermes_client):
        """Conversation should accept messages without context field."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.call_tool = AsyncMock(
                return_value={"content": "Response"}
            )
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation",
                json={"message": "Hi"},
            )

            assert response.status_code == 200


class TestHermesConversationStream:
    """Tests for POST /api/hermes/conversation/stream."""

    def test_stream_returns_sse_format(self, hermes_client):
        """Stream endpoint should return text/event-stream content type."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()

            # Create an async generator that yields tokens
            async def mock_stream(message, session_id=None):
                yield "Hello"
                yield " from"
                yield " Hermes"

            mock_server.stream_chat = mock_stream
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation/stream",
                json={"message": "Hello"},
            )

            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            # Read SSE events
            content = response.content.decode()
            assert "data: Hello" in content
            assert "data:  from" in content
            assert "data:  Hermes" in content

    def test_stream_sends_data_prefix(self, hermes_client):
        """Each SSE event should have 'data:' prefix."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()

            async def mock_stream(message, session_id=None):
                yield "token1"

            mock_server.stream_chat = mock_stream
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation/stream",
                json={"message": "Hello"},
            )

            content = response.content.decode()
            assert "data: token1" in content
            # SSE events end with double newline
            assert "\n\n" in content

    def test_stream_calls_stream_chat(self, hermes_client):
        """Stream endpoint should call server.stream_chat with the message."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()

            call_args = []

            async def mock_stream(message, session_id=None):
                call_args.append((message, session_id))
                yield "response"

            mock_server.stream_chat = mock_stream
            mock_get_server.return_value = mock_server

            hermes_client.post(
                "/api/hermes/conversation/stream",
                json={"message": "What is AI?"}
            )

            assert call_args[0][0] == "What is AI?"
            assert isinstance(call_args[0][1], str) and len(call_args[0][1]) > 0

    def test_stream_handles_errors_gracefully(self, hermes_client):
        """Stream endpoint should yield SSE error event on exception."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()

            async def mock_stream(message, session_id=None):
                yield "partial"
                raise RuntimeError("LLM connection dropped")

            mock_server.stream_chat = mock_stream
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation/stream",
                json={"message": "Hello"}
            )

            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            content = response.content.decode()
            assert "data: partial" in content
            assert "[ERROR]" in content
            assert "LLM connection dropped" in content


class TestToolEndpoint:
    """Tests for POST /api/hermes/tool."""

    def test_tool_success(self, hermes_client):
        """Tool endpoint should execute the specified tool."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.call_tool = AsyncMock(
                return_value={"content": "Tool executed"}
            )
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/tool",
                json={"tool": "read_file", "arguments": {"path": "test.py"}},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["content"] == "Tool executed"
            mock_server.call_tool.assert_awaited_once_with(
                "read_file", {"path": "test.py"}
            )

    def test_tool_default_empty_arguments(self, hermes_client):
        """Tool endpoint should use empty dict when arguments not provided."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.call_tool = AsyncMock(return_value={"content": "ok"})
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/tool",
                json={"tool": "get_opencode_status"},
            )

            assert response.status_code == 200
            mock_server.call_tool.assert_awaited_once_with(
                "get_opencode_status", {}
            )

    def test_tool_result_without_content_key(self, hermes_client):
        """Tool endpoint should str-convert result when 'content' key is missing."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.call_tool = AsyncMock(return_value={"status": "unknown"})
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/tool",
                json={"tool": "some_tool"},
            )

            assert response.status_code == 200
            assert "unknown" in response.json()["content"]


class TestHermesSessions:
    """Tests for Hermes session management and cancellation."""

    def test_conversation_returns_session_id(self, hermes_client):
        """Conversation should return the session_id from the server."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.call_tool = AsyncMock(
                return_value={"content": "Hello!", "session_id": "sess_123"}
            )
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation",
                json={"message": "Hello"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Hello!"
            assert data["session_id"] == "sess_123"

    def test_conversation_passes_session_id(self, hermes_client):
        """Conversation should forward the provided session_id to the server."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.call_tool = AsyncMock(
                return_value={"content": "ok", "session_id": "abc"}
            )
            mock_get_server.return_value = mock_server

            hermes_client.post(
                "/api/hermes/conversation",
                json={"message": "Hi", "session_id": "abc"},
            )

            mock_server.call_tool.assert_awaited_once_with(
                "chat", {"message": "Hi", "session_id": "abc"}
            )

    def test_stream_uses_provided_session_id(self, hermes_client):
        """Stream should forward the provided session_id to stream_chat."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()

            async def mock_stream(message, session_id=None):
                yield "Hello"

            mock_server.stream_chat = mock_stream
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation/stream",
                json={"message": "Hello", "session_id": "sess_abc"},
            )

            assert response.status_code == 200
            assert response.headers["X-Session-Id"] == "sess_abc"
    def test_stream_generates_session_header(self, hermes_client):
        """Stream should generate a session id and return it in the header."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()

            async def mock_stream(message, session_id=None):
                yield "Hello"

            mock_server.stream_chat = mock_stream
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation/stream",
                json={"message": "Hello"},
            )

            assert response.status_code == 200
            assert "X-Session-Id" in response.headers
            assert len(response.headers["X-Session-Id"]) == 12

    def test_cancel_endpoint_success(self, hermes_client):
        """Cancel endpoint should call server.cancel and report success."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.cancel.return_value = True
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation/cancel",
                json={"session_id": "sess_1"},
            )

            assert response.status_code == 200
            assert response.json() == {"success": True, "session_id": "sess_1"}
            mock_server.cancel.assert_called_once_with("sess_1")

    def test_cancel_endpoint_not_found(self, hermes_client):
        """Cancel endpoint should report success=False when no stream is active."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.cancel.return_value = False
            mock_get_server.return_value = mock_server

            response = hermes_client.post(
                "/api/hermes/conversation/cancel",
                json={"session_id": "nope"},
            )

            assert response.json() == {"success": False, "session_id": "nope"}

    def test_list_sessions(self, hermes_client):
        """Sessions endpoint should return the server's session list."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.list_sessions.return_value = [
                {"session_id": "s1", "message_count": 2},
            ]
            mock_get_server.return_value = mock_server

            response = hermes_client.get("/api/hermes/sessions")

            assert response.status_code == 200
            assert response.json() == {
                "sessions": [{"session_id": "s1", "message_count": 2}],
            }

    def test_delete_session(self, hermes_client):
        """Delete endpoint should clear the session and return success."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.clear_session.return_value = True
            mock_get_server.return_value = mock_server

            response = hermes_client.delete("/api/hermes/sessions/s1")

            assert response.status_code == 200
            assert response.json() == {"success": True, "session_id": "s1"}
            mock_server.clear_session.assert_called_once_with("s1")

    def test_delete_session_not_found(self, hermes_client):
        """Delete endpoint should 404 when the session does not exist."""
        with patch("backend.transport.routers.hermes.get_server") as mock_get_server:
            mock_server = MagicMock()
            mock_server.clear_session.return_value = False
            mock_get_server.return_value = mock_server

            response = hermes_client.delete("/api/hermes/sessions/nope")

            assert response.status_code == 404
