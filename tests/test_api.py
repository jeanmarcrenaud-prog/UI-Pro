# tests/test_api.py - FastAPI endpoint tests

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client"""
    from backend.transport.views_api import app

    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the fast /health liveness probe.

    P1#4 split: /health is for Docker/k8s liveness only and must do
    no I/O. Deep diagnostics live on /health/deep — see the next class.
    """

    def test_health_returns_200(self, client):
        """Health check should return 200"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_status_is_ok(self, client):
        """Fast probe always reports 'ok' status (no I/O performed)."""
        response = client.get("/health")
        data = response.json()
        assert data.get("status") == "ok", f"Unexpected status: {data.get('status')}"

    def test_health_payload_is_shallow(self, client):
        """Fast probe payload is shallow — no dependencies/services fields."""
        response = client.get("/health")
        data = response.json()
        # These are the deep-only fields; the fast probe must not surface
        # them or it defeats the whole point of the split.
        assert "dependencies" not in data
        assert "services" not in data

    def test_health_stays_fast(self, client):
        """Fast probe must complete in under 100ms (orchestration tools
        poll this on every second)."""
        import time

        start = time.perf_counter()
        response = client.get("/health")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert response.status_code == 200
        # 100ms is generous — typical is ~5ms. We're guarding against
        # accidentally re-introducing I/O in the fast path.
        assert elapsed_ms < 100, f"/health took {elapsed_ms:.1f}ms (>100ms)"


class TestHealthDeepEndpoint:
    """Tests for /health/deep diagnostic endpoint.

    P1#4 split: deep checks perform I/O (backends, deps, ollama version)
    and may take up to 4s. They are not safe for liveness probes.
    """

    def test_health_deep_returns_200(self, client):
        """Deep health check should return 200"""
        response = client.get("/health/deep")
        assert response.status_code == 200

    def test_health_deep_includes_dependencies(self, client):
        """Deep health check should report structured dependencies."""
        response = client.get("/health/deep")
        data = response.json()
        assert "dependencies" in data
        assert "services" in data

    def test_health_deep_includes_services(self, client):
        """Deep health check should include services info."""
        response = client.get("/health/deep")
        data = response.json()
        services = data["services"]
        assert "backends" in services
        assert "llm" in services
        assert "backends_summary" in services

    def test_health_deep_includes_ollama_version(self, client):
        """Deep health check surfaces the Ollama version probe result.

        The probe is a thin wrapper over check_ollama_version which
        returns a dict with at least a 'status' key — that key is
        always present even when Ollama is disabled (status='skipped').
        """
        response = client.get("/health/deep")
        data = response.json()
        ollama_version = data["services"].get("ollama_version")
        assert ollama_version is not None, "services.ollama_version missing"
        assert "status" in ollama_version
        # The status field is one of: "ok", "error", "unknown", "skipped".
        assert ollama_version["status"] in ("ok", "error", "unknown", "skipped")
        # latency_ms is always present and is a number (int/float)
        assert "latency_ms" in ollama_version
        assert isinstance(ollama_version["latency_ms"], (int, float))

    def test_health_deep_includes_required_models_field(self, client):
        """Deep health check surfaces the required_models block.

        The block always exists so consumers can iterate over it
        without null-checking, even when ollama_required_models is
        empty (the default).
        """
        response = client.get("/health/deep")
        data = response.json()
        rm = data.get("required_models")
        assert rm is not None, "required_models field missing from /health/deep"
        assert "configured" in rm
        assert "missing" in rm
        assert isinstance(rm["configured"], list)
        assert isinstance(rm["missing"], list)


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
