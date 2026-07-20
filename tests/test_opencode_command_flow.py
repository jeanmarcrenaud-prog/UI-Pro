import unittest
from unittest.mock import MagicMock
from backend.domain.core.models import ActiveFile, Cursor, Selection, Diagnostic
from backend.domain.core.editor_service import EditorService
from backend.domain.core.action_executor import ActionExecutor
from backend.application.intelligence.intelligence_service import IntelligenceService

class MockEditorState:
    def __init__(self):
        self.active_file = ActiveFile(path="test.py", content="print('hello')")
        self.cursor = Cursor(line=5, column=0)
        self.selection = None
        self.diagnostics = []
        self.terminal_output = ""
        self.git_status = {}

class MockEditorService:
    def get_current_state(self):
        return MockEditorState()

class TestOpenCodeIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_editor_service = MockEditorService()
        # On utilise le service mock qui renvoie un objet avec les bons attributs
        self.executor = ActionExecutor(self.mock_editor_service)
        self.intel_service = IntelligenceService(self.mock_editor_service, self.executor)

    def test_send_command_flow(self):
        # 1. Simuler une intention utilisateur
        intent = "Ajoute une ligne de code pour dire bonjour"
        
        # 2. Exécuter le plan
        result = self.intel_service.plan_and_execute(intent)
        
        # 3. Vérifier le résultat
        self.assertEqual(result["status"], "success")
        self.assertTrue(len(result["actions_performed"]) > 0)
        
        first_action = result["actions_performed"][0]
        self.assertEqual(first_action["status"], "success")
        print(f"Action générée : {first_action}")

if __name__ == "__main__":
    unittest.main()
