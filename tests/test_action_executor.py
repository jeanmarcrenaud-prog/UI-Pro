"""
Tests unitaires pour ActionExecutor (domaine Hermes).

Couvre tous les handlers d'actions locales :
  - insert_code
  - delete_code
  - move_cursor
  - run_terminal_command   (lancement réel non bloquant via subprocess.Popen)
  - open_file
  - rename_file

Et les chemins d'erreur (état manquant, params manquants, commande vide,
échec de lancement, action inconnue).
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from backend.domain.core.action_executor import ActionExecutor
from backend.domain.core.filesystem_service import FileContent


def _state_with(cursor=None, selection=None):
    """Construit un state dict comme celui renvoyé par EditorService.get_current_state."""
    return {
        "active_file": None,
        "cursor": cursor,
        "selection": selection,
        "diagnostics": [],
        "terminal_output": "",
        "git_status": "clean",
    }


class TestActionExecutorInsertCode(unittest.TestCase):
    def setUp(self):
        self.editor_service = MagicMock()
        self.filesystem_service = MagicMock()
        self.executor = ActionExecutor(self.editor_service, self.filesystem_service)

    def test_insert_code_success(self):
        self.editor_service.get_current_state.return_value = _state_with(
            cursor={"line": 10, "column": 5}
        )
        result = self.executor.execute_action("insert_code", {"content": "print('hi')"})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["action"], "insert_code")
        self.assertEqual(result["params"]["content"], "print('hi')")
        self.assertEqual(result["params"]["line"], 10)
        self.assertEqual(result["params"]["col"], 5)

    def test_insert_code_no_cursor(self):
        self.editor_service.get_current_state.return_value = _state_with(cursor=None)
        result = self.executor.execute_action("insert_code", {"content": "x"})
        self.assertEqual(result["status"], "error")
        self.assertIn("cursor", result["message"].lower())


class TestActionExecutorDeleteCode(unittest.TestCase):
    def setUp(self):
        self.editor_service = MagicMock()
        self.filesystem_service = MagicMock()
        self.executor = ActionExecutor(self.editor_service, self.filesystem_service)

    def test_delete_code_success(self):
        self.editor_service.get_current_state.return_value = _state_with(
            selection={"start_line": 1, "start_col": 0, "end_line": 3, "end_col": 10}
        )
        result = self.executor.execute_action("delete_code", {})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["action"], "delete_code")
        self.assertEqual(result["params"]["start_line"], 1)
        self.assertEqual(result["params"]["end_line"], 3)

    def test_delete_code_no_selection(self):
        self.editor_service.get_current_state.return_value = _state_with(selection=None)
        result = self.executor.execute_action("delete_code", {})
        self.assertEqual(result["status"], "error")
        self.assertIn("selection", result["message"].lower())


class TestActionExecutorMoveCursor(unittest.TestCase):
    def setUp(self):
        self.editor_service = MagicMock()
        self.filesystem_service = MagicMock()
        self.executor = ActionExecutor(self.editor_service, self.filesystem_service)

    def test_move_cursor_success(self):
        self.editor_service.get_current_state.return_value = _state_with()
        result = self.executor.execute_action("move_cursor", {"line": 42, "column": 7})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["action"], "move_cursor")
        self.assertEqual(result["params"]["line"], 42)
        self.assertEqual(result["params"]["col"], 7)

    def test_move_cursor_missing_params(self):
        self.editor_service.get_current_state.return_value = _state_with()
        result = self.executor.execute_action("move_cursor", {"line": 1})
        self.assertEqual(result["status"], "error")
        self.assertIn("line", result["message"].lower())


class TestActionExecutorRunTerminalCommand(unittest.TestCase):
    """Tests du handler run_terminal_command — lancement réel non bloquant."""

    def setUp(self):
        self.editor_service = MagicMock()
        self.filesystem_service = MagicMock()
        self.filesystem_service.root_dir = "/tmp/workspace"
        self.executor = ActionExecutor(self.editor_service, self.filesystem_service)
        # L'état éditeur est requis par execute_action avant d'appeler le handler
        self.editor_service.get_current_state.return_value = _state_with()

    def test_run_terminal_command_launches_process(self):
        """La commande est réellement lancée via subprocess.Popen (non bloquant)."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            result = self.executor.execute_action(
                "run_terminal_command", {"command": "notepad"}
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["action"], "run_terminal_command")
        self.assertEqual(result["params"]["command"], "notepad")
        self.assertEqual(result["params"]["pid"], 12345)

        # Popen a bien été appelé (pas seulement un dict retourné)
        mock_popen.assert_called_once()
        call_kwargs = mock_popen.call_args
        self.assertEqual(call_kwargs.args[0], "notepad")
        self.assertTrue(call_kwargs.kwargs["shell"])
        self.assertEqual(call_kwargs.kwargs["cwd"], "/tmp/workspace")
        # Non bloquant : on ne doit jamais appeler wait()/communicate()
        mock_proc.wait.assert_not_called()
        mock_proc.communicate.assert_not_called()

    def test_run_terminal_command_empty(self):
        result = self.executor.execute_action("run_terminal_command", {"command": ""})
        self.assertEqual(result["status"], "error")
        self.assertIn("command", result["message"].lower())

    def test_run_terminal_command_launch_failure(self):
        """Si Popen lève une exception, on retourne une erreur (pas de crash)."""
        with patch("subprocess.Popen", side_effect=OSError("command not found")):
            result = self.executor.execute_action(
                "run_terminal_command", {"command": "nonexistent_cmd_xyz"}
            )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["status"], "error")
        self.assertIn("Failed to run command", result["message"])

    def test_run_terminal_command_uses_filesystem_root_dir(self):
        """Le cwd est celui du filesystem_service.root_dir."""
        mock_proc = MagicMock()
        mock_proc.pid = 99
        self.filesystem_service.root_dir = "/custom/root"
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            self.executor.execute_action("run_terminal_command", {"command": "echo hi"})
        self.assertEqual(mock_popen.call_args.kwargs["cwd"], "/custom/root")


class TestActionExecutorOpenFile(unittest.TestCase):
    def setUp(self):
        self.editor_service = MagicMock()
        self.filesystem_service = MagicMock()
        self.executor = ActionExecutor(self.editor_service, self.filesystem_service)
        self.editor_service.get_current_state.return_value = _state_with()

    def test_open_file_success(self):
        self.filesystem_service.read_file.return_value = FileContent(
            path="main.py", content="print('hello')", last_modified=None, size=14
        )
        result = self.executor.execute_action("open_file", {"path": "main.py"})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["action"], "open_file")
        self.assertEqual(result["params"]["path"], "main.py")

    def test_open_file_not_found(self):
        self.filesystem_service.read_file.return_value = None
        result = self.executor.execute_action("open_file", {"path": "missing.py"})
        self.assertEqual(result["status"], "error")
        self.assertIn("missing.py", result["message"])


class TestActionExecutorRenameFile(unittest.TestCase):
    def setUp(self):
        self.editor_service = MagicMock()
        self.filesystem_service = MagicMock()
        self.executor = ActionExecutor(self.editor_service, self.filesystem_service)
        self.editor_service.get_current_state.return_value = _state_with()

    def test_rename_file_success(self):
        self.filesystem_service.rename_file.return_value = True
        result = self.executor.execute_action(
            "rename_file", {"current_path": "old.py", "new_name": "new.py"}
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["action"], "rename_file")
        self.assertEqual(result["params"]["current_path"], "./old.py")
        self.assertEqual(result["params"]["new_path"], ".\\new.py")

    def test_rename_file_failure(self):
        self.filesystem_service.rename_file.return_value = False
        result = self.executor.execute_action(
            "rename_file", {"current_path": "old.py", "new_name": "new.py"}
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("rename", result["message"].lower())


class TestActionExecutorEdgeCases(unittest.TestCase):
    def setUp(self):
        self.editor_service = MagicMock()
        self.filesystem_service = MagicMock()
        self.executor = ActionExecutor(self.editor_service, self.filesystem_service)

    def test_no_editor_state(self):
        """Sans état d'éditeur, toutes les actions locaux échouent proprement."""
        self.editor_service.get_current_state.return_value = None
        result = self.executor.execute_action("insert_code", {"content": "x"})
        self.assertEqual(result["status"], "error")
        self.assertIn("editor state", result["message"].lower())

    def test_unknown_action_type(self):
        self.editor_service.get_current_state.return_value = _state_with()
        result = self.executor.execute_action("nonexistent_action", {})
        self.assertEqual(result["status"], "error")
        self.assertIn("not implemented", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
