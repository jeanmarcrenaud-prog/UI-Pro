import asyncio
import logging
import unittest
from unittest.mock import MagicMock, AsyncMock
from typing import List, Dict, Any, Optional

# Correction des imports
from backend.application.intelligence.intelligence_service import IntelligenceService
from backend.domain.core.models import Action, HermesAction, DelegateAction, EditorState, Cursor
from backend.domain.core.action_executor import ActionExecutor
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestVoiceFlow(unittest.TestCase):
    def setUp(self):
        # Mock du connecteur
        self.mock_connector = MagicMock(spec=OpenCodeConnectorManager)
        self.mock_connector.run = AsyncMock(return_value={
            "success": True, "response": "Bonjour!", "session_id": "ses_test_001"
        })
        
        # Mock du service d'état
        self.mock_editor_service = MagicMock()
        self.mock_editor_service.get_current_state.return_value = {
            "cursor": {"line": 10, "column": 5},
            "selection": None
        }
        
        self.executor = ActionExecutor(self.mock_editor_service)
        
        # Mock Planner pour des intentions complexes (Délégation)
        self.mock_planner_complex = MagicMock()
        self.mock_planner_complex.generate_plan.side_effect = lambda intent, state: [
            DelegateAction(task=intent, status="delegated")
        ]

        self.mock_planner_simple = MagicMock()
        self.mock_planner_simple.generate_plan.side_effect = lambda intent, state: [
            HermesAction(action_type="insert_code", params={"content": "print('hello')"})
        ]

    def run_async(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_local_intent_returns_actions(self):
        """Les intents locaux sont exécutés via HermesAction -> ActionExecutor."""
        intelligence = IntelligenceService(
            planner=self.mock_planner_simple,
            executor=self.executor,
            connector_manager=self.mock_connector
        )
        
        state = EditorState(cursor=Cursor(line=10, column=5))
        actions = self.run_async(intelligence.process_voice_command("Ajoute un print", state))
        
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action_type, "insert_code")
        self.assertEqual(actions[0].params["content"], "print('hello')")

    def test_delegate_intent_calls_connector(self):
        """Les intents de délégation déclenchent connector_manager.run()."""
        intelligence = IntelligenceService(
            planner=self.mock_planner_complex,
            executor=self.executor,
            connector_manager=self.mock_connector
        )
        
        state = EditorState(cursor=Cursor(line=10, column=5))
        actions = self.run_async(intelligence.process_voice_command("Explique le code", state))
        
        self.mock_connector.run.assert_called_once_with("Explique le code", "workspace")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action_type, "opencode_delegate")
        self.assertEqual(actions[0].status, "success")

if __name__ == "__main__":
    unittest.main(verbosity=2)
