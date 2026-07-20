"""
test_mario.py - Tests for Mario Voice Assistant integration endpoints

Tests cover /api/mario/* endpoints: health, status, STT, TTS, conversation.
Mario services are mocked to avoid requiring the actual Mario project.
"""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from fastapi.testclient import TestClient


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture(scope="session")
def client():
    """Create FastAPI test client with rate limiting disabled."""
    import os
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    # Now import app — it will read RATE_LIMIT_ENABLED from env
    from backend.transport.main import app

    return TestClient(app)
    return TestClient(app)

@pytest.fixture
def mock_mario_available():
    """Mock MarioServices with all services available."""
    mock_tts = MagicMock()
    mock_tts.get_available_voices.return_value = ["fr_FR-siwis-medium", "en_US-lessac-medium"]
    mock_tts.speak.return_value = True
    mock_tts.test_synthesis.return_value = True

    mock_llm = MagicMock()
    mock_llm.service_type = "ollama"
    mock_llm.generate_response.return_value = "Bonjour ! Je suis Mario, votre assistant vocal."
    mock_llm.test_connection.return_value = True
    mock_llm.get_available_models.return_value = [
        "qwen3.5:9b", "llama3.2:3b", "mistral:7b",
    ]
    mock_llm.set_model.return_value = True

    from backend.transport.routers.mario import MarioServices

    services = MarioServices(
        tts=mock_tts,
        stt=None,
        llm=mock_llm,
        config=MagicMock(),
        settings=MagicMock(),
        available=True,
    )
    return services, mock_tts, mock_llm


@pytest.fixture
def mock_mario_unavailable():
    """Mock MarioServices as unavailable."""
    from backend.transport.routers.mario import MarioServices

    return MarioServices(available=False)


# ──────────────────────────────────────────────
# Tests: /api/mario/health
# ──────────────────────────────────────────────


class TestMarioHealth:
    """Tests for GET /api/mario/health"""

    def test_health_returns_200_when_available(self, client, mock_mario_available):
        """Health endpoint returns 200 when Mario is available."""
        services, _, _ = mock_mario_available
        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.get("/api/mario/health")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["tts"] is True
        assert data["llm"] is True

    def test_health_returns_200_when_unavailable(self, client, mock_mario_unavailable):
        """Health endpoint returns 200 even when Mario is unavailable."""
        with patch("backend.transport.routers.mario._get_mario", return_value=mock_mario_unavailable):
            response = client.get("/api/mario/health")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False

    def test_health_reports_llm_service_type(self, client, mock_mario_available):
        """Health endpoint reports the LLM service type."""
        services, _, mock_llm = mock_mario_available
        # Simulate LM Studio
        mock_llm.service_type = "lm_studio"

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.get("/api/mario/health")

        assert response.status_code == 200
        assert response.json()["llm_service"] == "lm_studio"


# ──────────────────────────────────────────────
# Tests: /api/mario/status
# ──────────────────────────────────────────────


class TestMarioStatus:
    """Tests for GET /api/mario/status"""

    def test_status_returns_full_info(self, client, mock_mario_available):
        """Status endpoint returns complete service info."""
        services, mock_tts, mock_llm = mock_mario_available

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.get("/api/mario/status")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["tts"] is True
        assert data["stt"] is False  # STT is loaded on demand
        assert data["llm"] is True
        assert data["llm_service"] == "ollama"
        assert "fr_FR-siwis-medium" in data["voices"]
        assert "qwen3.5:9b" in data["models"]

    def test_status_when_unavailable(self, client, mock_mario_unavailable):
        """Status endpoint reports correctly when Mario unavailable."""
        with patch("backend.transport.routers.mario._get_mario", return_value=mock_mario_unavailable):
            response = client.get("/api/mario/status")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert data["voices"] == []
        assert data["models"] == []

    def test_status_handles_tts_exception(self, client, mock_mario_available):
        """Status handles TTS failure gracefully (returns empty voices)."""
        services, mock_tts, _ = mock_mario_available
        mock_tts.get_available_voices.side_effect = Exception("TTS error")

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.get("/api/mario/status")

        assert response.status_code == 200
        assert response.json()["voices"] == []

    def test_status_handles_llm_exception(self, client, mock_mario_available):
        """Status handles LLM failure gracefully (returns empty models)."""
        services, _, mock_llm = mock_mario_available
        mock_llm.get_available_models.side_effect = Exception("LLM error")

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.get("/api/mario/status")

        assert response.status_code == 200
        assert response.json()["models"] == []


# ──────────────────────────────────────────────
# Tests: POST /api/mario/conversation
# ──────────────────────────────────────────────


class TestMarioConversation:
    """Tests for POST /api/mario/conversation"""

    def test_conversation_returns_response(self, client, mock_mario_available):
        """Conversation endpoint returns LLM response."""
        services, _, mock_llm = mock_mario_available
        mock_llm.generate_response.return_value = "Réponse test."

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/conversation",
                json={"message": "Bonjour", "temperature": 0.7},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Réponse test."
        assert data["service_type"] == "ollama"
        mock_llm.generate_response.assert_called_once_with(
            [{"role": "user", "content": "Bonjour"}], temperature=0.7
        )

    def test_conversation_with_model_override(self, client, mock_mario_available):
        """Conversation respects model override."""
        services, _, mock_llm = mock_mario_available
        mock_llm.generate_response.return_value = "Réponse."

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/conversation",
                json={"message": "Bonjour", "model": "llama3.2:3b"},
            )

        assert response.status_code == 200
        mock_llm.set_model.assert_called_once_with("llama3.2:3b")

    def test_conversation_empty_message_fails(self, client, mock_mario_available):
        """Empty message returns 400."""
        services, _, _ = mock_mario_available

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/conversation",
                json={"message": "", "temperature": 0.7},
            )

        assert response.status_code == 400

    def test_conversation_when_llm_unavailable(self, client, mock_mario_available):
        """Conversation returns 503 when LLM is not available."""
        services, _, _ = mock_mario_available
        services.llm = None

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/conversation",
                json={"message": "Bonjour", "temperature": 0.7},
            )

        assert response.status_code == 503

    def test_conversation_when_mario_unavailable(self, client, mock_mario_unavailable):
        """Conversation returns 503 when Mario not available."""
        with patch("backend.transport.routers.mario._get_mario", return_value=mock_mario_unavailable):
            response = client.post(
                "/api/mario/conversation",
                json={"message": "Bonjour", "temperature": 0.7},
            )

        assert response.status_code == 503

    def test_conversation_handles_llm_error(self, client, mock_mario_available):
        """Conversation handles LLM exception gracefully."""
        services, _, mock_llm = mock_mario_available
        mock_llm.generate_response.side_effect = Exception("LLM crashed")

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/conversation",
                json={"message": "Bonjour", "temperature": 0.7},
            )

        assert response.status_code == 500


# ──────────────────────────────────────────────
# Tests: POST /api/mario/tts/play
# ──────────────────────────────────────────────


class TestMarioTTSPlay:
    """Tests for POST /api/mario/tts/play"""

    def test_tts_play_success(self, client, mock_mario_available):
        """TTS play returns success when Mario speaks."""
        services, mock_tts, _ = mock_mario_available
        mock_tts.speak.return_value = True

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/tts/play",
                json={"text": "Bonjour le monde"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_tts.speak.assert_called_once_with("Bonjour le monde")

    def test_tts_play_empty_text_fails(self, client, mock_mario_available):
        """TTS play with empty text returns 400."""
        services, _, _ = mock_mario_available

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/tts/play",
                json={"text": "   "},
            )

        assert response.status_code == 400

    def test_tts_play_when_tts_unavailable(self, client, mock_mario_available):
        """TTS play returns 503 when TTS is not available."""
        services, _, _ = mock_mario_available
        services.tts = None

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/tts/play",
                json={"text": "Bonjour"},
            )

        assert response.status_code == 503


# ──────────────────────────────────────────────
# Tests: POST /api/mario/tts
# ──────────────────────────────────────────────


class TestMarioTTS:
    """Tests for POST /api/mario/tts"""

    def test_tts_empty_text_fails(self, client, mock_mario_available):
        """TTS with empty text returns 400."""
        services, _, _ = mock_mario_available

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/tts",
                json={"text": "", "voice": "fr_FR-siwis-medium"},
            )

        assert response.status_code == 400

    def test_tts_when_tts_unavailable(self, client, mock_mario_available):
        """TTS returns 503 when TTS is not available."""
        services, _, _ = mock_mario_available
        services.tts = None

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/tts",
                json={"text": "Bonjour", "voice": "fr_FR-siwis-medium"},
            )

        assert response.status_code == 503


# ──────────────────────────────────────────────
# Tests: POST /api/mario/stt
# ──────────────────────────────────────────────


class TestMarioSTT:
    """Tests for POST /api/mario/stt"""

    def test_stt_requires_file(self, client, mock_mario_available):
        """STT without file returns 422 (validation error)."""
        services, _, _ = mock_mario_available

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post("/api/mario/stt")

        assert response.status_code == 422

    def test_stt_when_mario_unavailable(self, client, mock_mario_unavailable):
        """STT returns 503 when Mario not available."""
        with patch("backend.transport.routers.mario._get_mario", return_value=mock_mario_unavailable):
            response = client.post(
                "/api/mario/stt",
                files={"audio": ("test.wav", io.BytesIO(b"fake-audio-data"), "audio/wav")},
                data={"language": "fr"},
            )

        assert response.status_code == 503

    def test_stt_empty_file_fails(self, client, mock_mario_available):
        """STT with empty file returns 400."""
        services, _, _ = mock_mario_available

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.post(
                "/api/mario/stt",
                files={"audio": ("empty.wav", io.BytesIO(b""), "audio/wav")},
                data={"language": "fr"},
            )

        assert response.status_code == 400


# ──────────────────────────────────────────────
# Tests: GET /api/mario/voices
# ──────────────────────────────────────────────


class TestMarioVoices:
    """Tests for GET /api/mario/voices"""

    def test_voices_returns_list(self, client, mock_mario_available):
        """Voices endpoint returns available TTS voices."""
        services, _, _ = mock_mario_available

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.get("/api/mario/voices")

        assert response.status_code == 200
        data = response.json()
        assert "voices" in data
        assert "fr_FR-siwis-medium" in data["voices"]

    def test_voices_when_tts_unavailable(self, client, mock_mario_available):
        """Voices returns 503 when TTS not available."""
        services, _, _ = mock_mario_available
        services.tts = None

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.get("/api/mario/voices")

        assert response.status_code == 503


# ──────────────────────────────────────────────
# Tests: GET /api/mario/models
# ──────────────────────────────────────────────


class TestMarioModels:
    """Tests for GET /api/mario/models"""

    def test_models_returns_list(self, client, mock_mario_available):
        """Models endpoint returns available LLM models."""
        services, _, _ = mock_mario_available

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.get("/api/mario/models")

        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "qwen3.5:9b" in data["models"]
        assert data["service_type"] == "ollama"

    def test_models_when_llm_unavailable(self, client, mock_mario_available):
        """Models returns 503 when LLM not available."""
        services, _, _ = mock_mario_available
        services.llm = None

        with patch("backend.transport.routers.mario._get_mario", return_value=services):
            response = client.get("/api/mario/models")

        assert response.status_code == 503


# ──────────────────────────────────────────────
# Tests: Router registration
# ──────────────────────────────────────────────


class TestMarioRouterRegistration:
    """Tests that the Mario router is properly registered."""

    def test_router_prefix(self):
        """Router uses correct prefix."""
        from backend.transport.routers.mario import router as mario_router

        assert mario_router.prefix == "/api/mario"

    def test_router_registered_in_app(self):
        """Mario router is registered in FastAPI app."""
        from backend.transport.main import app

        routes = [getattr(r, "path", "") for r in app.routes]
        assert "/api/mario/health" in routes
        assert "/api/mario/status" in routes
        assert "/api/mario/conversation" in routes
        assert "/api/mario/stt" in routes
        assert "/api/mario/tts" in routes
        assert "/api/mario/tts/play" in routes
        assert "/api/mario/voices" in routes
        assert "/api/mario/models" in routes

    def test_router_tags(self):
        """Router has correct tag."""
        from backend.transport.routers.mario import router as mario_router

        assert "mario" in mario_router.tags
