import asyncio
import logging
import unittest
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.editor_service import EditorService
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestSendActionFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.state_store = EditorStateStore()
        self.editor_service = EditorService(self.state_store)
        
        # Utilisation de l'URL locale par défaut
        self.manager = OpenCodeConnectorManager(
            uri="ws://localhost:8765",
            state_store=self.state_store,
            editor_service=self.editor_service
        )
        self.manager.set_editor_update_callback(lambda x: None)
        await self.manager.start()

    async def test_send_simple_action(self):
        """Vérifie que l'envoi d'une action vers le connecteur fonctionne."""
        # On tente d'envoyer une action d'insertion de code
        # Cette action doit être formatée par l'ActionExecutor avant d'être envoyée
        action_type = "insert_code"
        params = {
            "line": 5,
            "column": 0,
            "text": "print('Hello from Hermes!')"
        }
        
        logger.info(f"Tentative d'envoi de l'action : {action_type}")
        await self.manager.send_action(action_type, params)
        # Si le script n'échoue pas, l'appel a réussi à traverser le manager
        logger.info("L'appel send_action a réussi sans erreur.")

    async def asyncTearDown(self):
        await self.manager.stop()

if __name__ == "__main__":
    unittest.main()
