"""Adaptateur TTS branché sur la UI Mario (fallback local KittenTTS 2).

Le router ``backend/transport/routers/mario.py`` attend historiquement un objet
TTS exposant ``speak``, ``get_available_voices`` et ``synthesize_array`` (contrat
du ``TTSService`` externe du projet Mario). Quand le projet externe ``src/`` est
absent, on branche cet adaptateur qui délègue à :class:`KittenTTS2Service`
(moteur local, CPU uniquement, lazy-loadé).

Contrat public :
  * ``speak(text) -> bool`` : synthétise puis joue si un périphérique audio
    est disponible ; retourne ``False`` sans jamais lever d'exception.
  * ``get_available_voices() -> list[str]`` : voix du moteur ; fallback
    ``["KittenTTS2"]`` si vide (ne jamais casser le dropdown frontend).
  * ``synthesize_array(text) -> Optional[np.ndarray]`` : array mono 22050 Hz.
  * ``is_available`` : ``True`` si le moteur KittenTTS 2 est chargeable.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from backend.infrastructure.voice.audio_utils import TARGET_SAMPLE_RATE
from backend.infrastructure.voice.kittentts_service import KittenTTS2Service

logger = logging.getLogger(__name__)

# Voix de repli : garantit une liste non vide pour le dropdown même si le
# moteur local n'a pas encore été chargé.
_FALLBACK_VOICES = ["KittenTTS2"]


class MarioTTSAdapter:
    """Présente le contrat TTS attendu par ``mario.py`` (délègue à KittenTTS 2)."""

    def __init__(self, service: Optional[KittenTTS2Service] = None):
        # Création peu coûteuse : le modèle KittenTTS 2 est lazy-loadé au
        # premier appel réel (``synthesize`` / ``available_voices``).
        self._service = service if service is not None else KittenTTS2Service()

    # ── Disponibilité ───────────────────────────────────────────
    @property
    def is_available(self) -> bool:
        """``True`` si le moteur KittenTTS 2 est chargeable (ne crash jamais)."""
        try:
            return bool(self._service.is_available())
        except Exception as e:  # pragma: no cover - défensif
            logger.warning("Vérification KittenTTS 2 échouée : %s", e)
            return False

    # ── Introspection ───────────────────────────────────────────
    def get_available_voices(self) -> List[str]:
        """Voix du moteur ; fallback ``["KittenTTS2"]`` si aucune/indisponible."""
        try:
            voices = self._service.available_voices()
        except Exception as e:  # pragma: no cover - défensif
            logger.warning("Listing des voix KittenTTS 2 échoué : %s", e)
            voices = []
        return list(voices) if voices else list(_FALLBACK_VOICES)

    # ── Synthèse ────────────────────────────────────────────────
    def synthesize_array(self, text: str) -> Optional[np.ndarray]:
        """Génère un array mono à 22050 Hz, ou ``None`` si indisponible."""
        if not text:
            return None
        try:
            return self._service.synthesize(text)
        except Exception as e:  # pragma: no cover - défensif
            logger.error("Synthèse KittenTTS 2 échouée : %s", e)
            return None

    def speak(self, text: str) -> bool:
        """Synthétise puis joue l'audio si possible. Retourne ``False`` sinon."""
        audio = self.synthesize_array(text)
        if audio is None:
            return False
        return self._play(audio)

    @staticmethod
    def _play(audio: np.ndarray) -> bool:
        """Joue un array mono 22050 Hz via sounddevice (sinon ``False``)."""
        try:
            import sounddevice as sd
        except Exception as e:
            logger.warning("Lecture audio indisponible (sounddevice) : %s", e)
            return False

        try:
            sd.play(np.asarray(audio), TARGET_SAMPLE_RATE)
            sd.wait()
            return True
        except Exception as e:
            logger.error("Lecture audio échouée : %s", e)
            return False
