from typing import Optional
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.filesystem_service import FilesystemService

class EditorService:
    def __init__(self, state_store: EditorStateStore, filesystem_service: FilesystemService):
        self.state_store = state_store
        self.filesystem_service = filesystem_service

    def get_current_state(self) -> dict:
        """Récupère l'état actuel de l'éditeur sous forme de dictionnaire,
        enrichi par le contenu réel des fichiers via le FilesystemService."""
        state = self.state_store.get_state()
        
        # Enrichir l'état avec le contenu du fichier actif si disponible
        active_file_data = None
        if state.active_file:
            file_content = self.filesystem_service.read_file(state.active_file.path)
            if file_content:
                active_file_data = {
                    "path": file_content.path,
                    "content": file_content.content,
                    "last_modified": file_content.last_modified.isoformat()
                }

        return {
            "active_file": active_file_data,
            "cursor": state.cursor,
            "selection": state.selection,
            "diagnostics": state.diagnostics,
            "terminal_output": state.terminal_output,
            "git_status": state.git_status
        }
