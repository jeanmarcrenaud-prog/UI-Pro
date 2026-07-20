"""
Mario Voice Assistant Integration Router

Exposes Mario's STT (Whisper), TTS (Piper), and LLM capabilities
as FastAPI endpoints within UI-Pro.

Mario project path: ~/Documents/GitHub/Mario
"""

from __future__ import annotations

import os
import sys
import tempfile
import logging
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mario", tags=["mario"])

# ──────────────────────────────────────────────
# Mario project path resolution
# ──────────────────────────────────────────────
MARIO_PATH = os.path.expanduser("~/Documents/GitHub/Mario")


def _ensure_mario_path() -> bool:
    """Add Mario project to sys.path if not already present."""
    resolved = os.path.realpath(os.path.expanduser(MARIO_PATH))
    if not os.path.isdir(resolved):
        logger.warning("Mario project not found at %s", resolved)
        return False
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    return True


# ──────────────────────────────────────────────
# Lazy-loaded Mario service singletons
# ──────────────────────────────────────────────
@dataclass
class MarioServices:
    tts: Any = None
    stt: Any = None
    llm: Any = None
    config: Any = None
    settings: Any = None
    available: bool = False


_mario: MarioServices | None = None


def _get_mario() -> MarioServices:
    """Lazy-init Mario services. Returns empty services if Mario not found."""
    global _mario
    if _mario is not None:
        return _mario

    services = MarioServices(available=False)

    if not _ensure_mario_path():
        _mario = services
        return _mario

    try:
        from src.config.config import config as mario_config
        from src.models.settings import Settings
        from src.services.tts_service import TTSService
        from src.services.llm_service import LLMService

        services.config = mario_config
        services.settings = Settings.from_config(mario_config)

        # TTS — optional, may fail if Piper not installed
        try:
            services.tts = TTSService.create_with_piper(
                mario_config.DEFAULT_VOICE
            )
            logger.info("Mario TTS initialized")
        except Exception as e:
            logger.warning("Mario TTS unavailable: %s", e)

        # LLM — auto-detect Ollama / LM Studio / simulation
        try:
            services.llm = LLMService.detect_and_create()
            logger.info("Mario LLM initialized (%s)", services.llm.service_type)
        except Exception as e:
            logger.warning("Mario LLM unavailable: %s", e)

        # STT — optional, Whisper-heavy, init on first use
        # We import the adapter lazily in the endpoint

        services.available = True
    except ImportError as e:
        logger.warning("Mario import failed: %s — install Mario dependencies first", e)
    except Exception as e:
        logger.error("Mario initialization error: %s", e)

    _mario = services
    return _mario


# ──────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────


class ConversationRequest(BaseModel):
    message: str
    temperature: float = 0.7
    model: Optional[str] = None


class ConversationResponse(BaseModel):
    response: str
    service_type: str = "none"


class TTSRequest(BaseModel):
    text: str
    voice: str = "fr_FR-siwis-medium"


class StatusResponse(BaseModel):
    available: bool = False
    tts: bool = False
    stt: bool = False
    llm: bool = False
    llm_service: str = "none"
    voices: list[str] = []
    models: list[str] = []
    error: Optional[str] = None


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@router.get("/health")
async def mario_health():
    """Quick health check for Mario integration."""
    mario = _get_mario()
    return {
        "available": mario.available,
        "tts": mario.tts is not None,
        "llm": mario.llm is not None,
        "llm_service": mario.llm.service_type if mario.llm else "none",
    }


@router.get("/status", response_model=StatusResponse)
async def mario_status():
    """Full status of all Mario voice services."""
    mario = _get_mario()

    voices: list[str] = []
    if mario.tts:
        try:
            voices = mario.tts.get_available_voices()
        except Exception:
            voices = []

    models: list[str] = []
    if mario.llm:
        try:
            models = mario.llm.get_available_models()
        except Exception:
            models = []

    return StatusResponse(
        available=mario.available,
        tts=mario.tts is not None,
        stt=False,  # STT is loaded on demand
        llm=mario.llm is not None,
        llm_service=mario.llm.service_type if mario.llm else "none",
        voices=voices,
        models=models,
    )


@router.post("/stt")
async def speech_to_text(
    audio: UploadFile = File(...),
    language: str = Form("fr"),
):
    """
    Speech-to-text: upload an audio file → get transcription.

    Uses OpenAI Whisper via Mario's SpeechRecognitionService.
    Supported formats: wav, mp3, ogg, m4a, etc.
    """
    mario = _get_mario()
    if not mario.available:
        raise HTTPException(status_code=503, detail="Mario services not available")

    # Validate audio file
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file provided")

    # Save uploaded file to temp location
    suffix = Path(audio.filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Lazy import STT — Whisper is heavy
        from src.adapters.speech_recognition_whisper_adapter import (
            WhisperSpeechRecognitionAdapter,
        )
        from src.services.speech_recognition_service import (
            SpeechRecognitionService,
        )

        stt_adapter = WhisperSpeechRecognitionAdapter(model_name="base")
        stt_service = SpeechRecognitionService(speech_recognition_adapter=stt_adapter)

        text = stt_service.transcribe_file(tmp_path, language=language)
        return {"text": text, "language": language, "success": bool(text)}
    except ImportError as e:
        logger.error("STT import failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail="STT not available — install openai-whisper and torch",
        )
    except Exception as e:
        logger.error("STT transcription failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        # Cleanup temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    Text-to-speech: send text → receive audio file (WAV).

    Uses Piper TTS via Mario's TTSService.
    """
    mario = _get_mario()
    if not mario.tts:
        raise HTTPException(status_code=503, detail="TTS not available")

    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        # Create a temp output path for the audio
        out_path = tempfile.mktemp(suffix=".wav")

        # Use the TTS adapter to generate audio file
        # Piper's say() plays audio; for file generation we need
        # to use the lower-level TextToSpeech directly
        from src.models.text_to_speech import TextToSpeech

        tts = TextToSpeech()
        tts.load_voice(request.voice)

        # Generate audio to file
        import soundfile as sf
        import numpy as np

        audio_data = tts.synthesize(request.text)
        sf.write(out_path, audio_data, 22050)

        # Read and return the audio file
        with open(out_path, "rb") as f:
            audio_bytes = f.read()

        from fastapi.responses import Response

        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="mario-tts.wav"',
                "Content-Length": str(len(audio_bytes)),
            },
        )
    except ImportError as e:
        logger.error("TTS import failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail="TTS not available — install piper-tts and dependencies",
        )
    except Exception as e:
        logger.error("TTS synthesis failed: %s", e)
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
    finally:
        try:
            os.unlink(out_path)
        except (OSError, NameError, UnboundLocalError):
            pass


@router.post("/tts/play")
async def tts_play(request: TTSRequest):
    """
    Text-to-speech: send text → Mario speaks it aloud.

    Uses the system audio output (Piper TTS). This works when the
    server has audio hardware or a virtual audio device.
    """
    mario = _get_mario()
    if not mario.tts:
        raise HTTPException(status_code=503, detail="TTS not available")

    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        success = mario.tts.speak(request.text)
        if not success:
            raise HTTPException(status_code=500, detail="TTS playback failed")
        return {"success": True, "text": request.text[:100]}
    except Exception as e:
        logger.error("TTS playback failed: %s", e)
        raise HTTPException(status_code=500, detail=f"TTS playback failed: {e}")


@router.post("/conversation", response_model=ConversationResponse)
async def conversation(request: ConversationRequest):
    """
    Send a message to Mario's LLM and get a response.

    Uses auto-detected backend: Ollama → LM Studio → Simulation.
    """
    mario = _get_mario()
    if not mario.llm:
        raise HTTPException(status_code=503, detail="LLM not available")

    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Optionally switch model
    if request.model:
        mario.llm.set_model(request.model)

    try:
        messages = [{"role": "user", "content": request.message}]
        response = mario.llm.generate_response(
            messages, temperature=request.temperature
        )
        return ConversationResponse(
            response=response,
            service_type=mario.llm.service_type,
        )
    except Exception as e:
        logger.error("LLM conversation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")


@router.get("/voices")
async def list_voices():
    """List available TTS voices."""
    mario = _get_mario()
    if not mario.tts:
        raise HTTPException(status_code=503, detail="TTS not available")

    try:
        voices = mario.tts.get_available_voices()
        return {"voices": voices}
    except Exception as e:
        logger.error("Failed to list voices: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """List available LLM models from Mario's backend."""
    mario = _get_mario()
    if not mario.llm:
        raise HTTPException(status_code=503, detail="LLM not available")

    try:
        models = mario.llm.get_available_models()
        return {
            "models": models,
            "service_type": mario.llm.service_type,
        }
    except Exception as e:
        logger.error("Failed to list models: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
