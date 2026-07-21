import asyncio
import unittest
import os
from backend.domain.core.editor_state import InMemoryStateStore
from backend.domain.core.editor_service import EditorService
from backend.domain.core.filesystem_service import FilesystemService
from backend.domain.core.action_executor import ActionExecutor
from backend.application.intelligence.intelligence_service import init_intelligence_service, get_intelligence_service
from backend.application.intelligence.task_planner import TaskPlanner
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager
from backend.domain.core.models import EditorState, Cursor

class TestMcpFlow(unittest.TestCase):
    def setUp(self):
        self.filesystem_service = FilesystemService()
        self.state_store = InMemoryStateStore()
        self.editor_service = EditorService(self.state_store, self.filesystem_service)
        self.connector_manager = OpenCodeConnectorManager(self.editor_service, None)
        
        # Mock du Planner pour simuler une réponse LLM
        self.mock_planner = MockPlanner()
        
        # Initialisation de l'intelligence
        init_intelligence_service(self.mock_planner, ActionExecutor(self.editor_service, self.filesystem_service), self.connector_manager)
        self.intelligence_service = get_intelligence_service()

    def test_full_flow_creation_file(self):
        # 1. Simulation d'intention
        intent = "Crée un fichier hello.py avec un print hello"
        
        # 2. Traitement par l'intelligence
        actions = asyncio.run(self.intelligence_service.process_user_intent(intent, self.editor_service.get_current_state()))
        
        # Vérifier que le plan contient une action d'écriture
        self.assertTrue(any(a.action_type == "write_file" for a in actions))
        
        # 3. Exécution des actions
        for action in actions:
            if action.action_type == "write_file":
                res = self.editor_service.execute_action(action.action_type, action.params)
                self.assertEqual(res["status"], "success")
                
                # 4. Vérification physique sur le disque
                path = action.params.get("path")
                self.assertTrue(os.path.exists(path))
                with open(path, 'r') as f:
                    self.assertIn("print('hello')", f.read())

class MockPlanner:
    def generate_plan(self, intent, state):
        # Simule une décision LLM simple
        if "crée un fichier" in intent.lower():
            return [
                {
                    "action_type": "write_file", 
                    "params": {
                        "path": "hello.py", 
                        "content": "print('hello world')"
                    }
                }
            ]
        return []

if __name__ == "__main__":
    unittest.main()
