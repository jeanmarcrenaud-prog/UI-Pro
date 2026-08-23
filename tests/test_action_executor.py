"""
Tests unitaires pour ActionExecutor — mutations locales réelles.

Couvre :
  - insert_code / delete_code  → écriture fichier + curseur
  - move_cursor / open_file    → state_store
  - rename_file                → rename disque + sync active_file
  - run_terminal_command       → Popen non bloquant
  - chemins d'erreur
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.domain.core.action_executor import ActionExecutor
from backend.domain.core.editor_service import EditorService
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.filesystem_service import FileContent, FilesystemService
from backend.domain.core.models import ActiveFile, Cursor, Selection


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def workspace(tmp_path):
    """Répertoire workspace isolé pour chaque test."""
    root = tmp_path / "workspace"
    root.mkdir()
    return root


@pytest.fixture
def fs(workspace):
    return FilesystemService(root_dir=str(workspace))


@pytest.fixture
def store():
    return EditorStateStore()


@pytest.fixture
def editor(store, fs):
    return EditorService(state_store=store, filesystem_service=fs)


@pytest.fixture
def executor(editor, fs):
    return ActionExecutor(editor_service=editor, filesystem_service=fs)


def _write(fs: FilesystemService, path: str, content: str) -> None:
    assert fs.write_file(path, content) is True


def _seed_active(store: EditorStateStore, path: str, content: str, line: int = 1, col: int = 0):
    store.update(
        active_file=ActiveFile(path=path, content=content),
        cursor=Cursor(line=line, column=col),
        selection=None,
    )


# ── open_file ──────────────────────────────────────────────────────────────


class TestOpenFile:
    def test_open_file_success(self, executor, fs, store, workspace):
        _write(fs, "main.py", "print('hello')\n")
        result = executor.execute_action("open_file", {"path": "main.py"})

        assert result["status"] == "success"
        assert result["action"] == "open_file"
        assert result["params"]["path"] == "main.py"

        state = store.get_state()
        assert state.active_file is not None
        assert state.active_file.path == "main.py"
        assert state.cursor is not None
        assert state.cursor.line == 1
        assert state.cursor.column == 0
        assert state.selection is None

    def test_open_file_not_found(self, executor):
        result = executor.execute_action("open_file", {"path": "missing.py"})
        assert result["status"] == "error"
        assert "missing.py" in result["message"]

    def test_open_file_empty_path(self, executor, store):
        # besoin d'un state non-None
        result = executor.execute_action("open_file", {"path": ""})
        assert result["status"] == "error"
        assert "path" in result["message"].lower()


# ── move_cursor ────────────────────────────────────────────────────────────


class TestMoveCursor:
    def test_move_cursor_success(self, executor, store):
        result = executor.execute_action("move_cursor", {"line": 42, "column": 7})
        assert result["status"] == "success"
        assert result["params"]["line"] == 42
        assert result["params"]["col"] == 7

        cursor = store.get_state().cursor
        assert cursor is not None
        assert cursor.line == 42
        assert cursor.column == 7

    def test_move_cursor_accepts_col_alias(self, executor, store):
        result = executor.execute_action("move_cursor", {"line": 3, "col": 1})
        assert result["status"] == "success"
        assert store.get_state().cursor.column == 1

    def test_move_cursor_missing_params(self, executor):
        result = executor.execute_action("move_cursor", {"line": 1})
        assert result["status"] == "error"

    def test_move_cursor_invalid_position(self, executor):
        result = executor.execute_action("move_cursor", {"line": 0, "column": 0})
        assert result["status"] == "error"


# ── insert_code ────────────────────────────────────────────────────────────


class TestInsertCode:
    def test_insert_mid_line(self, executor, fs, store):
        _write(fs, "a.py", "hello world\n")
        _seed_active(store, "a.py", "hello world\n", line=1, col=6)

        result = executor.execute_action("insert_code", {"content": "XX"})
        assert result["status"] == "success"

        data = fs.read_file("a.py")
        assert data is not None
        assert data.content == "hello XXworld\n"

        cursor = store.get_state().cursor
        assert cursor.line == 1
        assert cursor.column == 8  # 6 + len("XX")

    def test_insert_multiline(self, executor, fs, store):
        _write(fs, "b.py", "line1\nline2\n")
        _seed_active(store, "b.py", "line1\nline2\n", line=1, col=5)

        result = executor.execute_action("insert_code", {"content": "\nINSERTED"})
        assert result["status"] == "success"

        data = fs.read_file("b.py")
        assert "INSERTED" in data.content

        cursor = store.get_state().cursor
        assert cursor.line == 2  # advanced after multi-line insert

    def test_insert_no_active_file(self, executor, store):
        store.update(cursor=Cursor(line=1, column=0), active_file=None)
        result = executor.execute_action("insert_code", {"content": "x"})
        assert result["status"] == "error"
        assert "active file" in result["message"].lower()

    def test_insert_no_cursor(self, executor, fs, store):
        _write(fs, "c.py", "abc\n")
        store.update(active_file=ActiveFile(path="c.py", content="abc\n"), cursor=None)
        result = executor.execute_action("insert_code", {"content": "x"})
        assert result["status"] == "error"
        assert "cursor" in result["message"].lower()

    def test_insert_empty_file(self, executor, fs, store):
        _write(fs, "empty.py", "")
        _seed_active(store, "empty.py", "", line=1, col=0)

        result = executor.execute_action("insert_code", {"content": "first"})
        assert result["status"] == "success"
        assert fs.read_file("empty.py").content == "first"


# ── delete_code ────────────────────────────────────────────────────────────


class TestDeleteCode:
    def test_delete_same_line(self, executor, fs, store):
        _write(fs, "d.py", "abcdef\n")
        store.update(
            active_file=ActiveFile(path="d.py", content="abcdef\n"),
            cursor=Cursor(line=1, column=0),
            selection=Selection(start_line=1, start_col=2, end_line=1, end_col=5),
        )

        result = executor.execute_action("delete_code", {})
        assert result["status"] == "success"

        data = fs.read_file("d.py")
        assert data.content == "abf\n"

        state = store.get_state()
        assert state.selection is None
        assert state.cursor.line == 1
        assert state.cursor.column == 2

    def test_delete_multi_line(self, executor, fs, store):
        _write(fs, "e.py", "aaa\nbbb\nccc\n")
        store.update(
            active_file=ActiveFile(path="e.py", content="aaa\nbbb\nccc\n"),
            cursor=Cursor(line=1, column=0),
            selection=Selection(start_line=1, start_col=1, end_line=3, end_col=1),
        )

        result = executor.execute_action("delete_code", {})
        assert result["status"] == "success"

        data = fs.read_file("e.py")
        # 'a' + 'cc\n'  (from start_col=1 of line1 through end_col=1 of line3)
        assert "bbb" not in data.content

    def test_delete_no_selection(self, executor, fs, store):
        _write(fs, "f.py", "x\n")
        _seed_active(store, "f.py", "x\n")
        result = executor.execute_action("delete_code", {})
        assert result["status"] == "error"
        assert "selection" in result["message"].lower()

    def test_delete_no_active_file(self, executor, store):
        store.update(
            selection=Selection(start_line=1, start_col=0, end_line=1, end_col=1),
            active_file=None,
        )
        result = executor.execute_action("delete_code", {})
        assert result["status"] == "error"
        assert "active file" in result["message"].lower()


# ── rename_file ────────────────────────────────────────────────────────────


class TestRenameFile:
    def test_rename_success(self, executor, fs, store, workspace):
        _write(fs, "old.py", "data\n")
        _seed_active(store, "old.py", "data\n")

        result = executor.execute_action(
            "rename_file", {"current_path": "old.py", "new_name": "new.py"}
        )
        assert result["status"] == "success"
        assert result["params"]["new_path"].endswith("new.py")

        assert fs.read_file("old.py") is None
        assert fs.read_file("new.py") is not None
        assert store.get_state().active_file.path == "new.py"

    def test_rename_missing_params(self, executor):
        result = executor.execute_action("rename_file", {"current_path": "a.py"})
        assert result["status"] == "error"

    def test_rename_failure(self, executor, fs):
        # source does not exist
        result = executor.execute_action(
            "rename_file", {"current_path": "ghost.py", "new_name": "x.py"}
        )
        assert result["status"] == "error"


# ── run_terminal_command ───────────────────────────────────────────────────


class TestRunTerminalCommand:
    def test_launches_process(self, executor, fs):
        mock_proc = MagicMock(pid=12345)
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            result = executor.execute_action(
                "run_terminal_command", {"command": "echo hi"}
            )

        assert result["status"] == "success"
        assert result["params"]["pid"] == 12345
        mock_popen.assert_called_once()
        assert mock_popen.call_args.kwargs["shell"] is True
        assert mock_popen.call_args.kwargs["cwd"] == fs.root_dir
        mock_proc.wait.assert_not_called()

    def test_empty_command(self, executor):
        result = executor.execute_action("run_terminal_command", {"command": ""})
        assert result["status"] == "error"

    def test_launch_failure(self, executor):
        with patch("subprocess.Popen", side_effect=OSError("not found")):
            result = executor.execute_action(
                "run_terminal_command", {"command": "nope"}
            )
        assert result["status"] == "error"
        assert "Failed to run command" in result["message"]


# ── edge cases ─────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_no_editor_state(self):
        editor = MagicMock()
        editor.get_current_state.return_value = None
        fs = MagicMock()
        executor = ActionExecutor(editor, fs)
        result = executor.execute_action("insert_code", {"content": "x"})
        assert result["status"] == "error"
        assert "editor state" in result["message"].lower()

    def test_unknown_action(self, executor):
        result = executor.execute_action("nonexistent_action", {})
        assert result["status"] == "error"
        assert "not implemented" in result["message"].lower()


# ── integration flow ───────────────────────────────────────────────────────


class TestMutationFlow:
    """open → move → insert → delete — flux bout-en-bout sur disque réel."""

    def test_open_move_insert_delete(self, executor, fs, store):
        _write(fs, "flow.py", "ABCDEF\n")

        assert executor.execute_action("open_file", {"path": "flow.py"})["status"] == "success"
        assert executor.execute_action("move_cursor", {"line": 1, "column": 3})["status"] == "success"
        assert executor.execute_action("insert_code", {"content": "XYZ"})["status"] == "success"

        content = fs.read_file("flow.py").content
        assert content == "ABCXYZDEF\n"

        # select "XYZ" (cols 3..6) and delete
        store.update(
            selection=Selection(start_line=1, start_col=3, end_line=1, end_col=6)
        )
        assert executor.execute_action("delete_code", {})["status"] == "success"
        assert fs.read_file("flow.py").content == "ABCDEF\n"