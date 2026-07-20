import asyncio
import logging
import numpy as np
import wave
import os
import json
import tempfile
from typing import Optional, List, Dict, Any, Callable, Awaitable
from backend.domain.core.models import EditorState
from backend.application.intelligence.intelligence_service import IntelligenceService
from backend.infrastructure.voice.stt_service import STTService
from backend.infrastructure.voice.tts_service import TTSService
from backend.infrastructure.voice.vad_service import VADService
from backend.infrastructure.voice.audio_capture_service import AudioCaptureService
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

logger = logging.getLogger(__name__)

class VoiceManager:
    """
    Orchestrateur de la pile vocale de Hermes.
    Gère le flux : Capture Audio -> VAD -> STT -> Intelligence -> Action -> TTS.
    Supervise également les retours d'OpenCode pour feedback vocal.
    """
    def __init__(
        self, 
        intelligence_service: IntelligenceService,
        stt_service: STTService,
        tts_service: TTSService,
        vad_service: VADService,
        audio_capture_service: AudioCaptureService,
        connector_manager: OpenCodeConnectorManager
    ):
        self.intelligence = intelligence_service
        self.stt = stt_service
        self.tts = tts_service
        self.vad = vad_service
        self.audio_capture = audio_capture_service
        self.connector_manager = connector_manager
        
        self.is_running = False
        self.audio_buffer = []
        self.is_speaking = False

        # Enregistrement du callback de feedback pour OpenCode
        self.connector_manager.register_callback(self._handle_opencode_notification)

    async def start(self):
        """Démarre la boucle de traitement vocal."""
        self.is_running = True
        logger.info("VoiceManager démarré.")
        
        # Lancer la capture audio en tâche de fond
        await self.audio_capture.start()
        self.audio_capture.on_audio_chunk = self._process_audio_chunk
        
        # Lancer la boucle principale de traitement
        asyncio.create_task(self._main_loop())

    async def stop(self):
        """Arrête les services vocaux."""
        self.is_running = False
        await self.audio_capture.stop()
        logger.info("VoiceManager arrêté.")

    async def _handle_opencode_notification(self, event: Dict[str, Any]):
        """
        Gère les notifications provenant d'OpenCode pour fournir un feedback vocal.
        """
        event_type = event.get("type")
        content = event.get("content", "")
        priority = event.get("priority", "low")

        if event_type == "error" or priority == "critical":
            logger.warning(f"Feedback vocal critique : {content}")
            # Optionnel : On pourrait utiliser le TTS ici pour alerter l'utilisateur immédiatement
            # await self.tts.speak(f"Attention, une erreur est survenue : {content}")
        
        elif event_type == "success" and priority == "high":
            logger.info(f"Feedback vocal succès : {content}")
            # On pourrait confirmer la réussite de la délégation
            # await self.tts.speak(f"L'action a été exécutée avec succès.")

    async def _process_audio_chunk(self, chunk: np.ndarray):
        """Callback reçu de la capture audio."""
        if self.vad.is_speech(chunk):
            self.audio_buffer.append(chunk)
        else:
            if len(self.audio_buffer) > 0:
                await self._process_speech_segment()

    async def _process_speech_segment(self):
        """Traitement d'un segment de parole capturé."""
        if not self.audio_buffer:
            return

        full_audio = np.concatenate(self.audio_buffer)
        self.audio_buffer = []

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            temp_path = tmp_file.name

        try:
            f = wave.open(temp_path, 'wb')
            f.setnchannels(1)
            f.setsampwidth(2)  # 16-bit = 2 bytes
            f.setframerate(16000)
            f.writeframes(full_audio.astype(np.int16).tobytes())
            f.close()
            
            transcript = await self.stt.transcribe(temp_path)
            
            if transcript and len(transcript.strip()) > 2:
                logger.info(f"Transcription reçue : {transcript}")
                
                # Intelligence & Action — pass a default EditorState
                state = EditorState()
                actions = await self.intelligence.process_voice_command(transcript, state)
                
                if actions:
                    for action in actions:
                        # OpenCodeConnectorManager.send_task takes a string — serialize the action
                        await self.connector_manager.send_task(
                            json.dumps({'type': action.action_type, 'params': action.params})
                        )
                        
        except Exception as e:
            logger.error(f"Erreur lors du traitement d'un segment vocal : {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def _main_loop(self):
        """Boucle principale qui analyse le flux audio."""
        while self.is_running:
            await asyncio.sleep(0.1)

# Singleton instance
_voice_manager: Optional[VoiceManager] = None

async def init_voice_manager(
    intelligence_service: IntelligenceService,
    stt_service: STTService,
    tts_service: TTSService,
    vad_service: VADService,
    audio_capture_service: AudioCaptureService,
    connector_manager: OpenCodeConnectorManager
):
    global _voice_manager
    _voice_manager = VoiceManager(
        intelligence_service,
        stt_service,
        tts_service,
        vad_service,
        audio_capture_service,
        connector_manager
    )
    await _voice_manager.start()

def get_voice_manager() -> VoiceManager:
    if _voice_manager is None:
        raise RuntimeError("VoiceManager n'est pas initialisé.")
    return _voice_manager
