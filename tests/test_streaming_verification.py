import unittest
import asyncio
import logging
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.editor_service import EditorService
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestStreamingVerification(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Initialisation des composants
        self.state_store = EditorStateStore()
        self.editor_service = EditorService(self.state_store)
        
        # Mocking du manager
        self.manager = OpenCodeConnectorManager(
            uri="ws://localhost:8080",
            state_store=self.state_store,
            editor_service=self.editor_service
        )
        self.manager.on_editor_update_callback = lambda x: None

    def test_terminal_streaming_flow(self):
        """Vérifie que le flux du terminal met à jour le store et le service."""
        mock_update = {
            "active_file": {"path": "main.py"},
            "cursor": {"line": 1, "column": 0},
            "selection": None,
            "diagnostics": [],
            "terminal": {"output": "Compiling... Success!"},
            "git": {}
        }
        
        self.manager._handle_update(mock_update)
        
        state = self.state_store.get_state()
        self.assertEqual(state.terminal_output, "Compiling... Success!")
        self.assertEqual(state.active_file.path, "main.py")
        
        service_state = self.editor_service.get_editor_state()
        self.assertEqual(service_state.terminal_output, "Compiling... Success!")

    def test_editor_update_flow(self):
        """Vérifie que le curseur et les diagnostics sont mis à jour."""
        mock_update = {
            "active_file": {"path": "test.py"},
            "cursor": {"line": 10, "column": 5},
            "selection": {"start_line": 9, "start_col": 0, "end_line": 9, "end_col": 10},
            "diagnostics": [{"line": 10, "message": "Syntax Error"}],
            "terminal": {"output": ""},
            "git": {}
        }
        
        self.manager._handle_update(mock_update)
        
        state = self.state_store.get_state()
        self.assertEqual(state.cursor.line, 10)
        self.assertEqual(state.cursor.column, 5)
        self.assertEqual(len(state.diagnostics), 1)
        self.assertEqual(state.diagnostics[0].message, "Syntax Error")

if __name__ == "__main__":
    unittest.main()
