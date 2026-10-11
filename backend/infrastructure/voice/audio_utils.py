"""Helpers audio pour la pile vocale.

Contrat cible : tout ce qui sort vers Mario doit être un ``np.ndarray`` mono
à **22050 Hz**. KittenTTS 2 peut produire du 16 kHz ou 24 kHz : on resample
donc dynamiquement, sans jamais hardcoder le sample rate du modèle.
"""

from __future__ import annotations

import logging
from math import gcd

import numpy as np

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 22050


def resample_to_22050(audio: np.ndarray, sr: int) -> np.ndarray:
    """Resample un ``np.ndarray`` mono vers 22050 Hz. Ne crash jamais.

    Ordre de préférence :
      1. ``scipy.signal.resample_poly`` — haute qualité, ratio rationnel exact.
      2. interpolation linéaire numpy — si scipy est indisponible.
      3. décimation entière — dernier recours (qualité moindre, loggée).
    """
    if audio is None:
        return audio  # type: ignore[return-value]

    try:
        audio = np.asarray(audio)
        if audio.size == 0 or not sr or int(sr) == TARGET_SAMPLE_RATE:
            return audio

        # Ratio rationnel réduit par le PGCD (ex : 24000 -> 147/160).
        divisor = gcd(TARGET_SAMPLE_RATE, int(sr))
        up = TARGET_SAMPLE_RATE // divisor
        down = int(sr) // divisor

        try:
            from scipy.signal import resample_poly

            return resample_poly(audio, up, down, axis=0)
        except Exception:
            logger.warning(
                "scipy indisponible ou resample_poly en échec — "
                "fallback interpolation numpy (qualité moindre)"
            )

        # Fallback : interpolation linéaire (accepte up/down sampling).
        n_out = int(round(len(audio) * TARGET_SAMPLE_RATE / float(sr)))
        if n_out <= 0:
            return audio
        x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
        return np.interp(x_new, x_old, audio)
    except Exception as exc:  # pragma: no cover - défensif
        logger.error("resample_to_22050 a échoué (%s) — décimation brute", exc)
        step = max(1, round(int(sr) / TARGET_SAMPLE_RATE)) if sr else 1
        return audio[::step] if step > 1 else audio
