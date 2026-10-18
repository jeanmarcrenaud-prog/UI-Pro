"""Adaptateur local KittenTTS 2 (TTS réel, CPU uniquement).

Objectif : remplacer le TTS *dummy* de ``TTSService`` par un vrai moteur
local, **sans toucher au GPU** (la VRAM est déjà occupée par LM Studio) et
avec un fallback robuste si ``kittenml`` n'est pas installé.

Contrat public :
  * ``KittenTTS2Service.synthesize(text) -> Optional[np.ndarray]``
    retourne un array mono **resample à 22050 Hz** (compatible
    ``sf.write(path, audio, 22050)``), ou ``None`` si indisponible.
  * Le modèle est **lazy-loadé au premier appel** (jamais au boot).
  * La voix FR est choisie **au runtime** dans ``available_voices`` — jamais
    hardcodée en dur comme réponse finale.
"""

from __future__ import annotations

import builtins
import io
import logging
import threading
from contextlib import contextmanager
from typing import List, Optional

import logging
import threading
from typing import List, Optional

import numpy as np

from backend.infrastructure.voice.audio_utils import (
    TARGET_SAMPLE_RATE,
    resample_to_22050,
)

logger = logging.getLogger(__name__)

# Modèle quantisé emb4 : ~506 Mo (vs 947 Mo non quantisé), même qualité perçue.
MODEL_ID = "KittenML/kitten-tts-2"
WEIGHTS = "emb4"

# Indices de voix francophones (ex : Hugo, Bruno, Kiki...). On ne hardcode pas
# une voix unique : le premier match dans ``available_voices`` gagne, sinon la
# première voix disponible est utilisée.
_FRENCH_VOICE_HINTS = (
    "fr",
    "french",
    "français",
    "francais",
    "hugo",
    "bruno",
    "kiki",
    "siwis",
    "claire",
    "colette",
)


@contextmanager
def _force_utf8_reads():
    """Force UTF-8 pendant la lecture des fichiers du modèle.

    Windows (cp1252) : kittenml lit ses fichiers de modèle avec l'encodage
    locale → `'charmap' codec can't decode byte 0x9d` au chargement.
    """
    original_open = builtins.open

    def _open_utf8(file, mode="r", *args, **kwargs):
        if "b" not in mode:
            args = list(args)
            # encoding = 4e positionnel de open() (file, mode, buffering, encoding…)
            if len(args) >= 2:
                if args[1] is None:
                    args[1] = "utf-8"
            elif kwargs.get("encoding") is None:
                kwargs["encoding"] = "utf-8"
            return original_open(file, mode, *args, **kwargs)
        return original_open(file, mode, *args, **kwargs)

    builtins.open = _open_utf8
    io.open = _open_utf8
    try:
        yield
    finally:
        builtins.open = original_open
        io.open = original_open


class KittenTTS2Service:
    """Wrapper CPU-only autour de ``kittenml.KittenTTS`` (lazy load)."""

    def __init__(self, model_id: str = MODEL_ID, weights: str = WEIGHTS):
        self.model_id = model_id
        self.weights = weights
        self._model = None
        self._load_failed = False
        self._voice: Optional[str] = None
        self._lock = threading.Lock()

    # ── Chargement ──────────────────────────────────────────────
    def _load(self):
        """Charge le modèle au premier appel. Retourne ``None`` si indispo."""
        if self._model is not None:
            return self._model
        if self._load_failed:
            return None

        with self._lock:
            # Double-checked locking : un seul chargement concurrent.
            if self._model is not None:
                return self._model
            if self._load_failed:
                return None

            try:
                from kittenml import KittenTTS  # import lazy — dépendance optionnelle
            except Exception as e:
                logger.warning("KittenTTS 2 indisponible (%s) — fallback dummy", e)
                self._load_failed = True
                return None

            try:
                with _force_utf8_reads():
                    model = KittenTTS(self.model_id, weights=self.weights)
                self._force_cpu(model)
                self._model = model
                logger.info(
                    "KittenTTS 2 chargé (model=%s, weights=%s, CPU).",
                    self.model_id,
                    self.weights,
                )
            except Exception as e:
                logger.error("Chargement KittenTTS 2 échoué : %s", e)
                self._load_failed = True
                return None

        return self._model

    @staticmethod
    def _force_cpu(model) -> None:
        """Force le backend sur CPU si un module torch est exposé."""
        try:
            if hasattr(model, "to"):
                model.to("cpu")
        except Exception:
            pass
        for attr in ("model", "module", "net"):
            inner = getattr(model, attr, None)
            if inner is not None and hasattr(inner, "to"):
                try:
                    inner.to("cpu")
                except Exception:
                    pass

    # ── Introspection ───────────────────────────────────────────
    @property
    def sample_rate(self) -> int:
        """Sample rate réel du modèle (fallback : 22050)."""
        return int(getattr(self._model, "sample_rate", TARGET_SAMPLE_RATE) or TARGET_SAMPLE_RATE)

    def is_available(self) -> bool:
        """``True`` si le moteur KittenTTS 2 est chargeable (lazy-load)."""
        return self._load() is not None

    def available_voices(self) -> List[str]:
        """Liste les voix du modèle (vide si indisponible)."""
        model = self._load()
        if model is None:
            return []
        try:
            return list(getattr(model, "available_voices", []) or [])
        except Exception:
            return []

    def select_french_voice(self) -> Optional[str]:
        """Choisit une voix FR naturelle, sinon la première disponible."""
        voices = self.available_voices()
        if not voices:
            return None
        for voice in voices:
            label = str(voice).lower()
            if any(hint in label for hint in _FRENCH_VOICE_HINTS):
                return voice
        return voices[0]

    # ── Synthèse ────────────────────────────────────────────────
    def synthesize(self, text: str, voice: Optional[str] = None) -> Optional[np.ndarray]:
        """Génère un array mono à 22050 Hz, ou ``None`` si indisponible.

        Si ``voice`` est fournie (ex : dropdown frontend), elle est utilisée ;
        sinon la voix FR auto-détectée est conservée.
        """
        if not text:
            return None

        model = self._load()
        if model is None:
            return None

        try:
            # Choix de voix : celle demandée si elle figure dans les voix du
            # modèle (ex : dropdown frontend), sinon la FR auto-détectée.
            voices = self.available_voices()
            if voice and voices and voice in voices:
                v = voice
            else:
                v = self.select_french_voice()
            self._voice = v
            audio = model.generate(text, **({"voice": v} if v else {}))
            audio = np.asarray(audio)

            sr = self.sample_rate
            if sr != TARGET_SAMPLE_RATE:
                audio = resample_to_22050(audio, sr)
            return audio
        except Exception as e:
            logger.error("Synthèse KittenTTS 2 échouée : %s", e)
            return None
