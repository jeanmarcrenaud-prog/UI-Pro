import os
from typing import Any, Dict, List, Optional
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.editor_service import EditorService
from backend.domain.core.filesystem_service import FilesystemService
from backend.domain.core.models import ActiveFile, Cursor, Selection

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

    @staticmethod
    def _as_dict(obj: Any) -> Dict[str, Any]:
        """Normalise un objet (dataclass ou dict) en dict pour accès .get()."""
        if obj is None:
            return {}
        if hasattr(obj, "__dataclass_fields__"):
            return {f: getattr(obj, f) for f in obj.__dataclass_fields__}
        if isinstance(obj, dict):
            return obj
        return {}

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
        elif action_type == "write_file":
            return self._handle_write_file(params, state)
        else:
            logger.warning(f"Action type {action_type} is not yet implemented.")
            return {
                "status": "error",
                "message": f"Action {action_type} not implemented"
            }

    def _handle_insert_code(self, content: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Insère du code à la position actuelle du curseur."""
        cursor = self._as_dict(state.get("cursor"))
        if not cursor:
            return {"status": "error", "message": "No cursor position available"}
        
        active_file_data = state.get("active_file")
        if not active_file_data:
            return {"status": "error", "message": "No active file"}
        
        file_path = active_file_data.get("path")
        file_content = active_file_data.get("content", "")
        line = cursor.get("line", 1)
        col = cursor.get("column", 0)
        
        # Insérer le contenu à la position du curseur
        lines = file_content.splitlines(keepends=True)
        if line < 1 or line > len(lines) + 1:
            return {"status": "error", "message": f"Invalid line {line}"}
        
        # Ajuster pour index 0-based
        idx = line - 1
        if idx < len(lines):
            target_line = lines[idx]
            if col < 0 or col > len(target_line):
                return {"status": "error", "message": f"Invalid column {col}"}
            lines[idx] = target_line[:col] + content + target_line[col:]
        else:
            # Insertion après la dernière ligne
            lines.append(content)
        
        new_content = "".join(lines)
        
        # Écrire sur le disque
        success = self.filesystem_service.write_file(file_path, new_content)
        if not success:
            return {"status": "error", "message": "Failed to write file"}
        
        # Calculer nouvelle position du curseur
        new_col = col + len(content)
        new_line = line
        # Si insertion multiligne, avancer les lignes
        if "\n" in content:
            new_line += content.count("\n")
            last_newline_idx = content.rindex("\n")
            new_col = len(content) - last_newline_idx - 1
        
        # Mettre à jour le store
        self.editor_service.state_store.update(
            active_file=ActiveFile(path=file_path, content=new_content),
            cursor=Cursor(line=new_line, column=new_col),
        )
        
        return {
            "status": "success",
            "action": "insert_code",
            "params": {
                "content": content,
                "line": line,
                "col": col
            }
        }

    def _handle_delete_code(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Supprime le texte actuellement sélectionné par l'utilisateur."""
        selection = self._as_dict(state.get("selection"))
        if not selection:
            return {"status": "error", "message": "No selection available"}
        
        active_file_data = state.get("active_file")
        if not active_file_data:
            return {"status": "error", "message": "No active file"}
        
        file_path = active_file_data.get("path")
        file_content = active_file_data.get("content", "")
        
        start_line = selection.get("start_line", 1)
        start_col = selection.get("start_col", 0)
        end_line = selection.get("end_line", 1)
        end_col = selection.get("end_col", 0)
        
        lines = file_content.splitlines(keepends=True)
        if start_line < 1 or start_line > len(lines) or end_line < 1 or end_line > len(lines):
            return {"status": "error", "message": "Invalid selection range"}
        
        # Supprimer la sélection
        start_idx = start_line - 1
        end_idx = end_line - 1
        
        if start_idx == end_idx:
            # Même ligne
            target_line = lines[start_idx]
            if start_col < 0 or end_col > len(target_line) or start_col > end_col:
                return {"status": "error", "message": "Invalid column range"}
            lines[start_idx] = target_line[:start_col] + target_line[end_col:]
            new_cursor_col = start_col
        else:
            # Multi-lignes: garder début de start_line + fin de end_line
            start_part = lines[start_idx][:start_col]
            end_part = lines[end_idx][end_col:]
            lines[start_idx] = start_part + end_part
            # Supprimer les lignes du milieu
            del lines[start_idx + 1:end_idx + 1]
            new_cursor_col = start_col
        
        new_content = "".join(lines)
        
        # Écrire sur le disque
        success = self.filesystem_service.write_file(file_path, new_content)
        if not success:
            return {"status": "error", "message": "Failed to write file"}
        
        # Mettre à jour le store: sélection effacée, curseur au début de la suppression
        self.editor_service.state_store.update(
            active_file=ActiveFile(path=file_path, content=new_content),
            cursor=Cursor(line=start_line, column=new_cursor_col),
            selection=None,
        )
        
        return {
            "status": "success",
            "action": "delete_code",
            "params": {
                "start_line": start_line,
                "start_col": start_col,
                "end_line": end_line,
                "end_col": end_col
            }
        }

    def _handle_move_cursor(self, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Déplace le curseur à une ligne et colonne spécifiques."""
        line = params.get("line")
        col = params.get("column") or params.get("col")
        if line is None or col is None:
            return {"status": "error", "message": "Line and Column are required"}
        if line < 1 or col < 0:
            return {"status": "error", "message": "Invalid line or column"}
        
        # Mettre à jour le curseur dans le store
        self.editor_service.state_store.update(cursor=Cursor(line=line, column=col))
        
        return {
            "status": "success",
            "action": "move_cursor",
            "params": {"line": line, "col": col}
        }

    def _handle_run_terminal(self, command: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute réellement une commande dans le terminal de manière non bloquante."""
        if not command:
            return {"status": "error", "message": "Command is required"}

        import subprocess

        # Répertoire de travail : dossier racine du filesystem (workspace par défaut)
        cwd = getattr(self.filesystem_service, "root_dir", None) or os.getcwd()

        try:
            # Lancement non bloquant : le processus tourne en arrière-plan,
            # le serveur ne bloque pas sur son exécution.
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.error(f"Échec du lancement de la commande '{command}': {e}")
            return {"status": "error", "message": f"Failed to run command: {e}"}

        logger.info(f"Commande lancée (pid={process.pid}): {command}")
        return {
            "status": "success",
            "action": "run_terminal_command",
            "params": {"command": command, "pid": process.pid}
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
        
        # Mettre à jour le store: active_file + curseur au début
        self.editor_service.state_store.update(
            active_file=ActiveFile(path=file_data.path, content=file_data.content),
            cursor=Cursor(line=1, column=0),
            selection=None,
        )
        
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
            # Mettre à jour active_file dans le store si c'était le fichier ouvert
            current_state = self.editor_service.state_store.get_state()
            stored_path = current_state.active_file.path if current_state.active_file else None
            # Comparer sans le préfixe ./ ni .\
            norm_stored = stored_path.lstrip("./\\\\") if stored_path else None
            norm_current = current_path.lstrip("./\\\\")
            if norm_stored and norm_stored == norm_current:
                # Stocker le chemin normalisé (sans ./ ni .\)
                clean_new_path = new_path.lstrip("./\\\\")
                self.editor_service.state_store.update(
                    active_file=ActiveFile(path=clean_new_path, content=current_state.active_file.content)
                )
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

    def _handle_write_file(self, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Crée ou écrase un fichier via le FilesystemService (mutation réelle)."""
        path = params.get("path")
        content = params.get("content", "")

        if not path:
            return {"status": "error", "message": "Path is required"}

        success = self.filesystem_service.write_file(path, content)
        if not success:
            return {"status": "error", "message": f"Failed to write file {path}"}

        # Si le fichier écrit est le fichier actif, synchroniser le store
        current_state = self.editor_service.state_store.get_state()
        if current_state.active_file and current_state.active_file.path == path:
            self.editor_service.state_store.update(
                active_file=ActiveFile(path=path, content=content)
            )

        return {
            "status": "success",
            "action": "write_file",
            "params": {"path": path}
        }