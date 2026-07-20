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


@dataclass
class HermesAction:
    """Action planifiée par le TaskPlanner avec son raisonnement."""
    action_type: str
    params: Dict[str, Any]
    reasoning: str = ""

@dataclass
class Action:
    action_type: str
    params: Dict[str, Any]
    status: str = "pending"
    message: Optional[str] = None

@dataclass
class DelegateAction:
    """Action spécifique pour la délégation à un agent externe (OpenCode)."""
    action_type: str = "opencode_delegate"
    task: str = ""
    status: str = "delegated"
    progress: float = 0.0
    response_text: Optional[str] = None

@dataclass
class OpenCodeProgress:
    """Modèle pour les notifications en temps réel d'OpenCode."""
    event_type: str  # e.g., "file_update", "token", "error"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
