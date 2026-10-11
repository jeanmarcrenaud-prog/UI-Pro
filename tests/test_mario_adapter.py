"""test_mario_adapter.py - Tests de l'adaptateur TTS local Mario (KittenTTS 2).

``kittenml`` n'est pas installé en CI : chaque test injecte un faux module via
``sys.modules`` (même stratégie que ``tests/test_kittentts.py``).

Scénarios couverts :
  1. Adaptateur dispo : ``synthesize_array`` -> array mono 22050 Hz.
  2. Voix FR : ``get_available_voices`` délègue au moteur.
  3. Moteur indisponible : fallback ``["KittenTTS2"]``, ``synthesize_array``
     -> ``None`` et ``speak`` -> ``False`` (aucun crash).
  4. ``_get_mario()`` branche l'adaptateur quand ``src/`` est absent.
  5. ``POST /api/mario/tts`` -> 503 si la synthèse retourne ``None``.
"""

from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pytest

from backend.infrastructure.voice.audio_utils import TARGET_SAMPLE_RATE
from backend.infrastructure.voice.mario_adapter import MarioTTSAdapter


def _install_fake_kittenml(voices, sample_rate, n_samples):
    """Injecte un faux module ``kittenml`` retournant un modèle canné."""
    model = MagicMock()
    model.sample_rate = sample_rate
    model.available_voices = list(voices)
    model.generate.return_value = np.ones(n_samples, dtype=np.float32)

    module = types.ModuleType("kittenml")
    setattr(module, "KittenTTS", MagicMock(return_value=model))
    return module, model


class TestMarioTTSAdapterAvailable:
    def test_synthesize_array_is_22050(self, monkeypatch):
        """Un modèle 24 kHz est resample vers le contrat 22050 Hz."""
        module, _ = _install_fake_kittenml(["Hugo"], 24000, 24000)
        monkeypatch.setitem(sys.modules, "kittenml", module)

        audio = MarioTTSAdapter().synthesize_array("Bonjour le monde")

        assert audio is not None
        assert isinstance(audio, np.ndarray)
        assert abs(len(audio) - TARGET_SAMPLE_RATE) <= 5

    def test_is_available_true_when_engine_present(self, monkeypatch):
        module, _ = _install_fake_kittenml(["Hugo"], TARGET_SAMPLE_RATE, 1000)
        monkeypatch.setitem(sys.modules, "kittenml", module)

        assert MarioTTSAdapter().is_available is True

    def test_get_available_voices_delegates_to_engine(self, monkeypatch):
        module, _ = _install_fake_kittenml(
            ["Hugo", "Bruno"], TARGET_SAMPLE_RATE, 1000
        )
        monkeypatch.setitem(sys.modules, "kittenml", module)

        assert MarioTTSAdapter().get_available_voices() == ["Hugo", "Bruno"]

    def test_speak_plays_and_returns_true(self, monkeypatch):
        module, _ = _install_fake_kittenml(["Hugo"], TARGET_SAMPLE_RATE, 1000)
        monkeypatch.setitem(sys.modules, "kittenml", module)

        fake_sd = types.ModuleType("sounddevice")
        fake_sd.play = MagicMock()
        fake_sd.wait = MagicMock()
        monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

        assert MarioTTSAdapter().speak("Bonjour") is True
        fake_sd.play.assert_called_once()


class TestMarioTTSAdapterUnavailable:
    def test_get_available_voices_fallback(self, monkeypatch):
        """Sans moteur : jamais une liste vide (le dropdown resterait cassé)."""
        monkeypatch.setitem(sys.modules, "kittenml", None)

        assert MarioTTSAdapter().get_available_voices() == ["KittenTTS2"]

    def test_synthesize_array_none_when_engine_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "kittenml", None)

        assert MarioTTSAdapter().synthesize_array("Bonjour") is None

    def test_speak_returns_false_without_audio(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "kittenml", None)

        assert MarioTTSAdapter().speak("Bonjour") is False

    def test_is_available_false_when_engine_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "kittenml", None)

        assert MarioTTSAdapter().is_available is False


class TestGetMarioFallback:
    def test_attaches_adapter_when_src_absent(self, monkeypatch):
        """``src/`` absent -> l'adaptateur KittenTTS 2 est branché."""
        import backend.transport.routers.mario as mario_router

        monkeypatch.setattr(mario_router, "_mario", None)
        monkeypatch.setattr(mario_router, "_ensure_mario_path", lambda: False)

        services = mario_router._get_mario()

        assert services.tts is not None
        assert services.available is True


class TestTtsEndpointFallback:
    def test_tts_endpoint_503_when_synthesis_returns_none(self, monkeypatch):
        """``/tts`` retourne 503 si le moteur ne produit aucun audio."""
        os.environ["RATE_LIMIT_ENABLED"] = "false"

        from fastapi.testclient import TestClient

        import backend.transport.routers.mario as mario_router
        from backend.transport.main import app

        mock_tts = MagicMock()
        mock_tts.synthesize_array.return_value = None
        services = mario_router.MarioServices(tts=mock_tts, available=True)
        monkeypatch.setattr(mario_router, "_get_mario", lambda: services)

        client = TestClient(app)
        response = client.post(
            "/api/mario/tts",
            json={"text": "Bonjour", "voice": "Hugo"},
        )

        assert response.status_code == 503
