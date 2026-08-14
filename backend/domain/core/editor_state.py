from typing import Any

from backend.domain.core.models import ActiveFile, Cursor, Diagnostic, EditorState, Selection
class EditorStateStore:
    """Stockage en mémoire pour l'état de l'éditeur durant les tests et le développement."""
    def __init__(self):
        self._state = EditorState()

    def get_state(self) -> EditorState:
        return self._state

    def set_state(self, state: EditorState):
        self._state = state

    def update(self, **kwargs: Any) -> None:
        """Met à jour partiellement l'état courant (champs fournis uniquement)."""
        for key, value in kwargs.items():
            if not hasattr(self._state, key):
                raise AttributeError(f"EditorState has no field {key!r}")
            setattr(self._state, key, value)

# Alias pour garantir la compatibilité avec tous les modules
InMemoryStateStore = EditorStateStore
