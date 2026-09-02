import logging
import numpy as np
import asyncio
from typing import Optional, Callable, Awaitable, TYPE_CHECKING

# pyaudio est une dépendance optionnelle (stack voice). On garde le module
# importable même sans PyAudio installé pour ne pas casser l'import du backend.
try:
    import pyaudio
    _PYAUDIO_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    pyaudio = None  # type: ignore[assignment]
    _PYAUDIO_AVAILABLE = False


if TYPE_CHECKING:
    from pyaudio import Stream as _Stream


logger = logging.getLogger(__name__)

class AudioCaptureService:
    """
    Service responsable de la capture du flux audio du microphone.
    Il fournit un flux de buffers audio bruts.
    """
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 1024, channels: int = 1):
        if not _PYAUDIO_AVAILABLE:
            raise ImportError(
                "pyaudio est requis pour la capture audio. "
                "Installez `pyaudio` (voir requirements.txt).")
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.p = pyaudio.PyAudio()
        self.stream: Optional[_Stream] = None
        self.on_audio_chunk: Optional[Callable[[np.ndarray], Awaitable[None]]] = None

    def _audio_callback(self, in_data, frame_count, time_info, status) -> tuple[bytes | None, int]:
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        if self.on_audio_chunk:
            # On utilise create_task car le callback de PyAudio est bloquant/synchrone
            # et nous voulons une exécution asynchrone sans bloquer le thread d'audio.
            asyncio.create_task(self._dispatch_audio_chunk(audio_data))
        return (None, pyaudio.paContinue)

    async def _dispatch_audio_chunk(self, audio_data: np.ndarray) -> None:
        if self.on_audio_chunk:
            await self.on_audio_chunk(audio_data)

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
