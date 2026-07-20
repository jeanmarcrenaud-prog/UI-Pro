from typing import Optional
from backend.domain.core.editor_state import EditorStateStore

class EditorService:
    def __init__(self, state_store: EditorStateStore):
        self.state_store = state_store

    def get_current_state(self) -> dict:
        """Récupère l'état actuel de l'éditeur sous forme de dictionnaire."""
        state = self.state_store.get_state()
        return {
            "active_file": state.active_file,
            "cursor": state.cursor,
            "selection": state.selection,
            "diagnostics": state.diagnostics,
            "terminal_output": state.terminal_output,
            "git_status": state.git_status
        }
