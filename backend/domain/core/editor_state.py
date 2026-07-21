from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class ActiveFile:
    path: str
    content: Optional[str] = None
    last_modified: datetime = field(default_factory=datetime.now)

@dataclass
class Cursor:
    line: int
    column: int

@dataclass
class Selection:
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    text: Optional[str] = None

@dataclass
class Diagnostic:
    line: int
    message: str
    severity: Optional[str] = None
    col: Optional[int] = None
    source: Optional[str] = None

@dataclass
class EditorState:
    active_file: Optional[ActiveFile] = None
    cursor: Optional[Cursor] = None
    selection: Optional[Selection] = None
    diagnostics: List[Diagnostic] = field(default_factory=list)
    terminal_output: Optional[str] = None
    git_status: Optional[Dict[str, Any]] = None

class InMemoryStateStore:
    """Stockage en mémoire pour l'état de l'éditeur durant les tests et le développement."""
    def __init__(self):
        self._state = EditorState()

    def get_state(self) -> EditorState:
        return self._state

    def set_state(self, state: EditorState):
        self._state = state
