import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

class TTSService:
    """
    Service de conversion Text-to-Speech (TTS).
    Prévu pour utiliser Piper ou un moteur local équivalent pour une voix naturelle.
    """
    def __init__(self, voice_model: str = "en_US-lessac-medium", output_dir: str = "voice_cache"):
        """
        :param voice_model: Nom du modèle de voix à utiliser.
        :param output_dir: Dossier où enregistrer les fichiers audio générés.
        """
        self.voice_model = voice_model
        self.output_dir = output_dir
        # Adaptateur KittenTTS 2 — lazy-loadé au premier appel (CPU only).
        self._kitten = None
        self._kitten_attempted = False
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        logger.info(f"TTS Service initialisé avec le modèle {voice_model}")

    def _get_kitten_service(self):
        """Lazy-init de l'adaptateur KittenTTS 2 (None si indisponible)."""
        if not self._kitten_attempted:
            self._kitten_attempted = True
            try:
                from backend.infrastructure.voice.kittentts_service import (
                    KittenTTS2Service,
                )

                self._kitten = KittenTTS2Service()
                logger.info("Adaptateur KittenTTS 2 initialisé (lazy, CPU).")
            except Exception as e:  # pragma: no cover - dépend de l'environnement
                logger.warning(
                    "KittenTTS 2 indisponible — fallback TTS dummy : %s", e
                )
                self._kitten = None
        return self._kitten

    def _dummy_path(self, text: str) -> str:
        """Chemin de sortie du fallback dummy (contrat existant)."""
        filename = f"tts_{hash(text) % 10000}.wav"
        return os.path.join(self.output_dir, filename)

    def synthesize_array(self, text: str) -> Optional[np.ndarray]:
        """Retourne un np array mono à 22050 Hz (pour Mario /tts).

        Retourne None si KittenTTS 2 n'est pas disponible : l'appelant peut
        alors retomber sur le comportement dummy.
        """
        if not text:
            return None

        kitten = self._get_kitten_service()
        if kitten is None:
            return None

        audio = kitten.synthesize(text)
        if audio is None:
            return None
        return audio

    def synthesize(self, text: str) -> Optional[str]:
        """
        Convertit du texte en fichier audio.
        :param text: Le texte à convertir en voix.
        :return: Le chemin vers le fichier audio généré.
        """
        if not text:
            return None

        output_path = self._dummy_path(text)

        try:
            # Moteur local réel : KittenTTS 2 (CPU), resample vers 22050 Hz.
            audio = self.synthesize_array(text)
            if audio is not None:
                import soundfile as sf

                sf.write(output_path, audio, 22050)
                logger.debug(f"Synthèse KittenTTS 2 : '{text}' -> {output_path}")
                return output_path

            # Fallback dummy (KittenTTS 2 absent) — contrat inchangé.
            logger.debug(f"Synthèse du texte (dummy) : '{text}' -> {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Erreur lors de la synthèse TTS : {e}")
            return None
