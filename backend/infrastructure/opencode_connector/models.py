from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Cursor(BaseModel):
    line: int
    column: int

class Selection(BaseModel):
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    text: str

class Diagnostic(BaseModel):
    severity: str  # Error, Warning, Info
    message: str
    line: int
    col: int
    source: Optional[str] = None

class ActiveFile(BaseModel):
    path: str
    content: str

class EditorUpdate(BaseModel):
    active_file: Optional[ActiveFile] = None
    cursor: Optional[Cursor] = None
    selection: Optional[Selection] = None
    diagnostics: List[Diagnostic] = Field(default_factory=list)
    terminal: Optional[Dict[str, Any]] = None
    git: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)

class HermesAction(BaseModel):
    action: str  # insert_code, delete_selection, move_cursor, run_terminal_command, open_file, git_commit
    params: Dict[str, Any]

class OpenCodeResponse(BaseModel):
    status: str  # success, error, pending
    data: Dict[str, Any]
    error_message: Optional[str] = None
