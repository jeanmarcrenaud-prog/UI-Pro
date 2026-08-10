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
                "chat", {"message": "Hello"}
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
            async def mock_stream(message):
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

            async def mock_stream(message):
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

            async def mock_stream(message):
                call_args.append(message)
                yield "response"

            mock_server.stream_chat = mock_stream
            mock_get_server.return_value = mock_server

            hermes_client.post(
                "/api/hermes/conversation/stream",
                json={"message": "What is AI?"}
            )

            assert call_args == ["What is AI?"]


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
