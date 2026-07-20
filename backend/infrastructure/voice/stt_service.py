import logging
import torch
from faster_whisper import WhisperModel
from typing import Optional

logger = logging.getLogger(__name__)

class STTService:
    """
    Service de conversion Speech-to-Text utilisant Faster-Whisper.
    Optimisé pour l'exécution locale sur GPU (RTX 5080).
    """
    def __init__(self, model_size: str = "base", device: str = "cuda"):
        """
        :param model_size: Taille du modèle (ex: 'tiny', 'base', 'small', 'medium')
        :param device: 'cuda' pour GPU ou 'cpu'
        """
        try:
            # Vérification de la disponibilité du GPU
            if device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA n'est pas disponible, passage automatique en CPU.")
                device = "cpu"
                compute_type = "int8"
            else:
                compute_type = "float16" if device == "cuda" else "int8"

            # Initialisation du modèle Faster-Whisper
            # 'base' est un bon équilibre entre vitesse et précision pour des commandes de code
            self.model = WhisperModel(
                model_size, 
                device=device, 
                compute_type=compute_type
            )
            logger.info(f"STT Service initialisé avec le modèle {model_size} sur {device}")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du STT : {e}")
            raise

    def transcribe(self, audio_path: str) -> Optional[str]:
        """
        Transcrit un fichier audio en texte.
        :param audio_path: Chemin vers le fichier audio (.wav, .mp3)
        :return: Texte transcrit ou None en cas d'erreur
        """
        try:
            segments, _ = self.model.transcribe(audio_path, beam_size=5)
            full_text = " ".join([segment.text for segment in segments])
            return full_text.strip()
        except Exception as e:
            logger.error(f"Erreur lors de la transcription : {e}")
            return None
