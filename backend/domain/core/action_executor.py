import os
from typing import Any, Dict, List, Optional
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.editor_service import EditorService
from backend.domain.core.filesystem_service import FilesystemService

import logging
logger = logging.getLogger(__name__)

class ActionExecutor:
    """
    Service de domaine responsable de la transformation d'intentions
    en actions concrètes pilotant l'éditeur via le protocole OpenCode.
    """
    def __init__(self, editor_service: EditorService, filesystem_service: FilesystemService):
        self.editor_service = editor_service
        self.filesystem_service = filesystem_service

    def execute_action(self, action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Point d'entrée principal pour l'exécution d'une action.
        Transforme une intention en une action conforme au protocole JSON.
        """
        logger.info(f"Executing action: {action_type} with params: {params}")
        
        state = self.editor_service.get_current_state()
        if not state:
            return {"status": "error", "message": "No editor state available"}

        if action_type == "insert_code":
            return self._handle_insert_code(params.get("content", ""), state)
        elif action_type == "delete_code":
            return self._handle_delete_code(state)
        elif action_type == "move_cursor":
            return self._handle_move_cursor(params, state)
        elif action_type == "run_terminal_command":
            return self._handle_run_terminal(params.get("command", ""), state)
        elif action_type == "open_file":
            return self._handle_open_file(params.get("path", ""), state)
        elif action_type == "rename_file":
            return self._handle_rename_file(params, state)
        else:
            logger.warning(f"Action type {action_type} is not yet implemented.")
            return {
                "status": "error",
                "message": f"Action {action_type} not implemented"
            }

    def _handle_insert_code(self, content: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Insère du code à la position actuelle du curseur."""
        cursor = state.get("cursor")
        if not cursor:
            return {"status": "error", "message": "No cursor position available"}
        
        return {
            "status": "success",
            "action": "insert_code",
            "params": {
                "content": content,
                "line": cursor.get("line"),
                "col": cursor.get("column")
            }
        }

    def _handle_delete_code(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Supprime le texte actuellement sélectionné par l'utilisateur."""
        selection = state.get("selection")
        if not selection:
            return {"status": "error", "message": "No selection available"}
        
        return {
            "status": "success",
            "action": "delete_code",
            "params": {
                "start_line": selection.get("start_line"),
                "start_col": selection.get("start_col"),
                "end_line": selection.get("end_line"),
                "end_col": selection.get("end_col")
            }
        }

    def _handle_move_cursor(self, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Déplace le curseur à une ligne et colonne spécifiques."""
        line = params.get("line")
        col = params.get("column")
        if line is None or col is None:
            return {"status": "error", "message": "Line and Column are required"}
            
        return {
            "status": "success",
            "action": "move_cursor",
            "params": {"line": line, "col": col}
        }

    def _handle_run_terminal(self, command: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute une commande dans le terminal."""
        if not command:
            return {"status": "error", "message": "Command is required"}
            
        return {
            "status": "success",
            "action": "run_terminal_command",
            "params": {"command": command}
        }

    def _handle_open_file(self, path: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Ouvre un fichier spécifique via le FilesystemService."""
        if not path:
            return {"status": "error", "message": "Path is required"}
        
        file_data = self.filesystem_service.read_file(path)
        if not file_data:
            return {
                "status": "error",
                "message": f"File {path} not found"
            }
            
        return {
            "status": "success",
            "action": "open_file",
            "params": {"path": path}
        }

    def _handle_rename_file(self, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Renomme un fichier via le FilesystemService."""
        current_path = params.get("current_path")
        new_name = params.get("new_name")
        
        if not current_path or not new_name:
            return {"status": "error", "message": "current_path and new_name are required"}
        
        # Construction du nouveau chemin
        if not current_path.startswith("./") and not current_path.startswith("/"):
            current_path = "./" + current_path
            
        new_path = os.path.join(os.path.dirname(current_path), new_name)
        
        success = self.filesystem_service.rename_file(current_path, new_path)
        
        if success:
            return {
                "status": "success",
                "action": "rename_file",
                "params": {
                    "current_path": current_path,
                    "new_path": new_path
                }
            }
        else:
            return {
                "status": "error",
                "message": "Failed to rename file"
            }
