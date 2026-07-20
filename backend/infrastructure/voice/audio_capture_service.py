import logging
import numpy as np
import pyaudio
import asyncio
from typing import Optional, Callable, Awaitable
from backend.domain.core.models import EditorUpdate

logger = logging.getLogger(__name__)

class AudioCaptureService:
    """
    Service responsable de la capture du flux audio du microphone.
    Il fournit un flux de buffers audio bruts.
    """
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 1024, channels: int = 1):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.p = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.on_audio_chunk: Optional[Callable[[np.ndarray], Awaitable[None]]] = None

    def _audio_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        if self.on_audio_chunk:
            # On utilise create_task car le callback de PyAudio est bloquant/synchrone
            # et nous voulons une exécution asynchrone sans bloquer le thread d'audio.
            asyncio.create_task(self.on_audio_chunk(audio_data))

    async def start(self):
        """Démarre le flux de capture."""
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback
        )
        logger.info(f"Capture audio démarrée (Rate: {self.sample_rate}, Chunk: {self.chunk_size})")

    async def stop(self):
        """Arrête le flux de capture."""
        if self.stream:
            await self.stream.stop_stream()
            await self.stream.close()
        self.p.terminate()
        logger.info("Capture audio arrêtée.")
