import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from backend.domain.core.models import HermesAction
from backend.domain.core.action_executor import ActionExecutor
from backend.application.intelligence.intelligence_service import IntelligenceService
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager


class MockEditorService:
    def __init__(self):
        self.state_store = MagicMock()
    def get_current_state(self):
        return {
            "active_file": {"path": "test.py", "content": "line1\nline2\nline3\nline4\n"},
            "cursor": {"line": 5, "column": 0},
            "selection": None
        }

class TestOpenCodeIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_editor_service = MockEditorService()
        self.executor = ActionExecutor(self.mock_editor_service, MagicMock())
        self.mock_connector = MagicMock(spec=OpenCodeConnectorManager)

        # Local planner: the intent is fulfilled by a HermesAction executed locally.
        self.mock_planner = AsyncMock()
        self.mock_planner.generate_plan.side_effect = lambda intent, state: [
            HermesAction(action_type="insert_code", params={"content": "print('hello')"})
        ]

        self.intel_service = IntelligenceService(
            planner=self.mock_planner,
            executor=self.executor,
            connector_manager=self.mock_connector,
        )

    def run_async(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_send_command_flow(self):
        # 1. Simuler une intention utilisateur
        intent = "Ajoute une ligne de code pour dire bonjour"

        # 2. Exécuter le plan via l'API courante (process_user_intent)
        state = self.mock_editor_service.get_current_state()
        actions = self.run_async(self.intel_service.process_user_intent(intent, state))

        # 3. Vérifier le résultat
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action_type, "insert_code")
        self.assertEqual(actions[0].status, "success")
        self.assertEqual(actions[0].params["content"], "print('hello')")
        # A local intent must not touch the OpenCode connector.
        self.mock_connector.run_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
