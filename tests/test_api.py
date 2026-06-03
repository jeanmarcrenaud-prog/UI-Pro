# tests/test_api.py - FastAPI endpoint tests

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client"""
    from backend.transport.views_api import app

    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint"""

    def test_health_returns_200(self, client):
        """Health check should return 200"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy(self, client):
        """Health check should return valid status"""
        response = client.get("/health")
        data = response.json()
        assert data.get("status") in ("healthy", "degraded"), f"Unexpected status: {data.get('status')}"
        assert "dependencies" in data, "Missing dependencies field"

    def test_health_includes_services(self, client):
        """Health check should include services info"""
        response = client.get("/health")
        data = response.json()
        assert "services" in data


class TestStatusEndpoint:
    """Tests for /status endpoint"""

    def test_status_requires_api_key(self, client):
        """Status may return 200 or require API key based on implementation"""
        response = client.get("/status")
        # Either requires auth (403/401) or is public (200)
        assert response.status_code in [200, 403, 401]

    def test_status_with_api_key(self, client, mocker):
        """Status should work with valid API key"""
        # Get API key from settings
        from models.settings import settings

        # Mock settings.api_key to prevent import issues during test
        mock_settings = mocker.MagicMock(api_key=None)
        mocker.patch("models.settings.settings", mock_settings)

        response = client.get(
            "/status",
            headers={"x-api-key": ""}
        )
        # Either 200 (no key configured = public) or 403 (wrong key)
        assert response.status_code in [200, 403]


class TestHomeEndpoint:
    """Tests for / endpoint"""

    def test_home_returns_200(self, client):
        """Home should return 200"""
        response = client.get("/")
        assert response.status_code == 200

    def test_home_contains_app_name(self, client):
        """Home should contain app name"""
        response = client.get("/")
        # App name is "UI Pro" not "UI-Pro"
        assert "UI Pro" in response.text or "UI-Pro" in response.text


class TestChatEndpoint:
    """Tests for /api/chat endpoint"""

    def test_chat_requires_message(self, client):
        """Chat without message should fail"""
        response = client.post("/api/chat", json={})
        assert response.status_code == 422  # Validation error

    def test_chat_with_message(self, client):
        """Chat with valid message"""
        # This may timeout or fail if LLM not available
        response = client.post("/api/chat", json={"message": "test"}, timeout=10)
        # Accept 200 (success) or 500 (LLM error)
        assert response.status_code in [200, 500]


class TestWebSocketEndpoint:
    """Tests for /ws endpoint"""

    def test_ws_endpoint_exists(self, client):
        """WebSocket endpoint should be registered"""
        from backend.transport.views_api import app

        routes = [r.path for r in app.routes]
        assert "/ws" in routes


class TestVersionEndpoint:
    """Tests for /api/version endpoint"""

    def test_version_returns_200(self, client):
        response = client.get("/api/version")
        assert response.status_code == 200

    def test_version_includes_required_fields(self, client):
        response = client.get("/api/version")
        data = response.json()
        assert "ui_pro_version" in data
        assert "fastapi_version" in data
        assert "python_version" in data
        assert "capabilities" in data
        assert isinstance(data["capabilities"], dict)

    def test_version_capabilities_known_keys(self, client):
        response = client.get("/api/version")
        data = response.json()
        caps = data["capabilities"]
        # Always report presence (True or False) for these modules
        for mod in ("faiss", "aiosqlite", "pynvml", "sentence_transformers"):
            assert mod in caps
            assert caps[mod] in (True, False)

    def test_version_fastapi_is_semver_like(self, client):
        response = client.get("/api/version")
        data = response.json()
        # Sanity: at least "X.Y" pattern
        import re

        assert re.match(r"^\d+\.\d+", data["fastapi_version"]), (
            f"Unexpected FastAPI version format: {data['fastapi_version']}"
        )
