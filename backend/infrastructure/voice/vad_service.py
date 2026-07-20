import logging
import torch
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

class VADService:
    """
    Service de détection d'activité vocale (VAD) utilisant Silero VAD.
    Permet de détecter quand l'utilisateur commence et finit de parler.
    """
    def __init__(self, device: str = "cuda"):
        """
        :param device: 'cuda' pour GPU ou 'cpu'
        """
        try:
            self.device = device
            # Chargement du modèle Silero VAD
            # Le modèle est chargé via torch pour une exécution locale rapide
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers-void/silero-vad',
                model='silero_vad',
                 Lombard=False # Optionnel: ajustement selon l'environnement
            )
            self.model.to(torch.device(device))
            self.model.eval()
            logger.info(f"VAD Service initialisé sur {device}")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du VAD : {e}")
            raise

    def is_speech(self, audio_data: np.ndarray) -> bool:
        """
        Détecte si le morceau d'audio contient de la parole.
        :param audio_data: Données audio en format float32 (ex: 16000Hz)
        :return: True si de la parole est détectée, False sinon.
        """
        try:
            # Silero VAD attend généralement des chunks de 512 samples
            with torch.no_grad():
                # Conversion en tensor si nécessaire
                if not isinstance(audio_data, torch.Tensor):
                    audio_tensor = torch.from_numpy(audio_data).to(self.device)
                else:
                    audio_tensor = audio_data.to(self.device)

                # Calcul du score de probabilité
                probability = self.model(audio_tensor, self.utils.get_speech_timestamps).probs
                return probability > 0.5
        except Exception as e:
            logger.error(f"Erreur lors de la détection VAD : {e}")
            return False
