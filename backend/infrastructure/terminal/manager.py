import logging
from typing import Dict, Any, List
from backend.domain.core.editor_state import EditorStateStore

logger = logging.getLogger(__name__)

class TerminalManager:
    """
    Gère la réception et le stockage des flux de terminal provenant du connecteur.
    Permet au LLM de lire les sorties des commandes exécutées en temps réel.
    """
    def __init__(self, state_store: EditorStateStore):
        self.state_store = state_store
        self.terminal_history: List[str] = []

    def process_stream(self, chunk: str):
        """
        Traite un morceau de flux terminal (terminal_stream).
        Ajoute le contenu au buffer et met à jour l'état global.
        """
        if not chunk:
            return

        self.terminal_history.append(chunk)
        full_output = "\n".join(self.terminal_history)[-10000:]  # Limiter la taille du buffer
        
        # Mise à jour du store
        self.state_store.update(terminal_output=full_output)
        logger.debug(f"Terminal output updated: {len(full_output)} chars")

    def get_last_output(self) -> str:
        return "\n".join(self.terminal_history)[-10000:]
