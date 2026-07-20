from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from threading import Lock
from .models import ActiveFile, Cursor, Selection, Diagnostic

@dataclass
class EditorState:
    """Représente l'état actuel de l'éditeur à un instant T."""
    active_file: Optional[ActiveFile] = None
    cursor: Optional[Cursor] = None
    selection: Optional[Selection] = None
    diagnostics: List[Diagnostic] = field(default_factory=list)
    terminal_output: Optional[str] = None
    git_status: Dict[str, Any] = field(default_factory=dict)

class EditorStateStore:
    """Stockage thread-safe de l'état de l'éditeur mis à jour par le connecteur."""
    def __init__(self):
        self._state = EditorState()
        self._lock = Lock()

    def update(self, active_file: Optional[ActiveFile] = None,
                cursor: Optional[Cursor] = None,
                selection: Optional[Selection] = None,
                diagnostics: Optional[List[Diagnostic]] = None,
                terminal_output: Optional[str] = None,
                git_status: Optional[Dict[str, Any]] = None):
        """Met à jour l'état avec les nouvelles données reçues."""
        with self._lock:
            if active_file:
                self._state.active_file = active_file
            if cursor:
                self._state.cursor = cursor
            if selection:
                self._state.selection = selection
            if diagnostics is not None:
                self._state.diagnostics = diagnostics
            if terminal_output is not None:
                self._state.terminal_output = terminal_output
            if git_status is not None:
                self._state.git_status = git_status

    def get_state(self) -> EditorState:
        """Retourne une copie de l'état actuel."""
        with self._lock:
            return EditorState(
                active_file=self._state.active_file,
                cursor=self._state.cursor,
                selection=self._state.selection,
                diagnostics=list(self._state.diagnostics),
                terminal_output=self._state.terminal_output,
                git_status=dict(self._state.git_status)
            )
