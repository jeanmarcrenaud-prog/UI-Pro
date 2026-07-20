import logging
from typing import Optional, List
from backend.domain.core.models import HermesAction

logger = logging.getLogger(__name__)

class VoiceService:
    """Interface de base pour les services de voix (STT, TTS, VAD)."""
    pass

class SpeechToTextService(VoiceService):
    """Convertit l'audio en texte."""
    async def transcribe(self, audio_data: bytes) -> str:
        # À implémenter avec Whisper ou autre
        return "Transcription simulée"

class TextToSpeechService(VoiceService):
    """Convertit le texte en audio."""
    async def synthesize(self, text: str) -> bytes:
        # À implémenter avec Edge-TTS ou ElevenLabs
        return b"Données audio simulées"

class VoiceActivityDetector(VoiceService):
    """Détecte si quelqu'un parle."""
    def is_speaking(self, audio_chunk: bytes) -> bool:
        # À implémenter avec Silero VAD ou équivalent
        return True
