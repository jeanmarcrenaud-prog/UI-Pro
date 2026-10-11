"""test_kittentts.py - Tests de l'intégration KittenTTS 2.

``kittenml`` n'est pas installé en CI : chaque test injecte un faux module
via ``sys.modules`` afin que le loader lazy de l'adaptateur le découvre.
Scénarios couverts :
  1. KittenTTS 2 dispo + sample rate != 22050 -> resample vers 22050 Hz.
  2. KittenTTS 2 indisponible -> ``TTSService`` retombe sur le chemin dummy.
  3. Une voix FR est sélectionnée automatiquement dans ``available_voices``.
"""

from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pytest

from backend.infrastructure.voice.audio_utils import (
    TARGET_SAMPLE_RATE,
    resample_to_22050,
)
from backend.infrastructure.voice.kittentts_service import KittenTTS2Service
from backend.infrastructure.voice.tts_service import TTSService


def _install_fake_kittenml(voices, sample_rate, n_samples):
    """Injecte un faux module ``kittenml`` retournant un modèle canné."""
    model = MagicMock()
    model.sample_rate = sample_rate
    model.available_voices = list(voices)
    model.generate.return_value = np.ones(n_samples, dtype=np.float32)

    module = types.ModuleType("kittenml")
    setattr(module, "KittenTTS", MagicMock(return_value=model))
    return module, model


class TestKittenTTSAvailable:
    def test_sample_rate_resampled_to_22050(self, monkeypatch):
        """Un modèle 24 kHz est resample vers le contrat 22050 Hz."""
        module, model = _install_fake_kittenml(["Hugo"], 24000, 24000)
        monkeypatch.setitem(sys.modules, "kittenml", module)

        service = KittenTTS2Service()
        audio = service.synthesize("Bonjour le monde")

        assert audio is not None
        assert isinstance(audio, np.ndarray)
        # 24000 samples @24k -> ~22050 samples @22050 (tolérance arrondi).
        assert abs(len(audio) - TARGET_SAMPLE_RATE) <= 5
        # La voix FR a bien été transmise au modèle.
        assert model.generate.call_args.kwargs.get("voice") == "Hugo"

        # Le helper de resample respecte lui aussi la cible.
        direct = resample_to_22050(np.ones(24000, dtype=np.float32), 24000)
        assert abs(len(direct) - TARGET_SAMPLE_RATE) <= 5


class TestKittenTTSUnavailable:
    def test_fallback_to_dummy_path(self, monkeypatch, tmp_path):
        """Sans ``kittenml``, ``synthesize()`` retourne le chemin dummy."""
        # ``None`` dans sys.modules force un ImportError au lazy-load.
        monkeypatch.setitem(sys.modules, "kittenml", None)

        service = TTSService(output_dir=str(tmp_path))
        path = service.synthesize("Bonjour")

        assert path is not None
        assert path.endswith(".wav")
        assert os.path.dirname(path) == str(tmp_path)
        # Aucun signal audio réel n'est produit sans KittenTTS 2.
        assert service.synthesize_array("Bonjour") is None


class TestFrenchVoiceSelection:
    def test_french_voice_auto_selected(self, monkeypatch):
        """Une voix francophone est choisie — jamais une valeur hardcodée."""
        module, model = _install_fake_kittenml(
            ["James", "Bruno", "Kiki", "Alice"], TARGET_SAMPLE_RATE, 2205
        )
        monkeypatch.setitem(sys.modules, "kittenml", module)

        service = KittenTTS2Service()
        audio = service.synthesize("Salut")

        assert audio is not None
        assert service._voice in {"Bruno", "Kiki"}
        assert model.generate.call_args.kwargs.get("voice") in {"Bruno", "Kiki"}
