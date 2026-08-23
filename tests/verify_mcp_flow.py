import asyncio
import unittest
import os
from unittest.mock import MagicMock
from backend.domain.core.editor_state import InMemoryStateStore
from backend.domain.core.editor_service import EditorService
from backend.domain.core.filesystem_service import FilesystemService
from backend.domain.core.action_executor import ActionExecutor
from backend.application.intelligence.intelligence_service import init_intelligence_service, get_intelligence_service
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager
from backend.domain.core.models import HermesAction

class TestMcpFlow(unittest.TestCase):
    def setUp(self):
        self.filesystem_service = FilesystemService()
        self.state_store = InMemoryStateStore()
        self.editor_service = EditorService(self.state_store, self.filesystem_service)
        self.connector_manager = MagicMock(spec=OpenCodeConnectorManager)

        # Mock du Planner pour simuler une réponse LLM
        self.mock_planner = MockPlanner()

        # Initialisation de l'intelligence avec l'ActionExecutor branché
        init_intelligence_service(
            self.mock_planner,
            ActionExecutor(self.editor_service, self.filesystem_service),
            self.connector_manager,
        )
        self.intelligence_service = get_intelligence_service()

    def tearDown(self):
        # Nettoyage du fichier généré dans le workspace
        target = os.path.join(self.filesystem_service.root_dir, "hello.py")
        if os.path.exists(target):
            os.remove(target)

    def test_full_flow_creation_file(self):
        # 1. Simulation d'intention
        intent = "Crée un fichier hello.py avec un print hello"

        # 2. Traitement par l'intelligence : plan -> exécution réelle via ActionExecutor
        actions = asyncio.run(
            self.intelligence_service.process_user_intent(intent, self.editor_service.get_current_state())
        )

        # Vérifier que le plan a produit une action d'écriture exécutée avec succès
        self.assertTrue(any(a.action_type == "write_file" for a in actions))
        write_action = next(a for a in actions if a.action_type == "write_file")
        self.assertEqual(write_action.status, "success")

        # 3. Vérification physique sur le disque (mutation réelle)
        path = os.path.join(self.filesystem_service.root_dir, "hello.py")
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as f:
            self.assertIn("print('hello world')", f.read())

class MockPlanner:
    async def generate_plan(self, intent, state):
        # Simule une décision LLM simple
        if "crée un fichier" in intent.lower():
            return [
                HermesAction(
                    action_type="write_file",
                    params={
                        "path": "hello.py",
                        "content": "print('hello world')"
                    }
                )
            ]
        return []

if __name__ == "__main__":
    unittest.main()
