import asyncio
import json
import logging
import threading
import time
import unittest
import sys
import os

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("integration_test")

# Correction robuste du PYTHONPATH
# On remonte jusqu'à la racine du projet (où se trouve le dossier 'backend')
current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)
# On remonte de 2 niveaux (tests -> ui-pro)
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from backend.domain.core.editor_state import EditorStateStore
    from backend.domain.core.editor_service import EditorService
    from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager
    from backend.domain.core.action_executor import ActionExecutor
    from backend.domain.core.models import EditorUpdate, HermesAction
except ImportError as e:
    logger.error(f"Erreur d'importation : {e}")
    logger.error(f"Chemin de recherche : {sys.path}")
    sys.exit(1)

# --- Mock WebSocket Server ---
class MockOpenCodeServer:
    """Simule un serveur OpenCode qui envoie des mises à jour."""
    def __init__(self):
        self.clients = []
        self.running = True

    async def handle_client(self, reader, writer):
        self.clients.append((reader, writer))
        logger.info("Client connecté au Mock Server")
        try:
            while self.running:
                await asyncio.sleep(1)
                # Simuler une mise à jour de l'éditeur toutes les secondes
                update_data = {
                    "active_file": {"path": "/mock/path/file.py", "content": "print('hello')"},
                    "cursor": {"line": 1, "column": 10},
                    "selection": {"start_line": 1, "start_col": 0, "end_line": 1, "end_col": 10, "text": "print('hello')"},
                    "diagnostics": [],
                    "terminal": {"output": "Success"},
                    "git": {"branch": "master", "is_dirty": False}
                }
                msg = json.dumps({"editor_update": update_data})
                writer.write(msg.encode())
                await writer.drain()
        except Exception as e:
            logger.error(f"Erreur Mock Server : {e}")
        finally:
            writer.close()

    async def run(self, host='127.0.0.1', port=8000):
        server = await asyncio.start_server(self.handle_client, host, port)
        logger.info(f"Mock Server lancé sur {host}:{port}")
        async with server:
            await server.serve_forever()

# --- Test Suite ---
class TestOpenCodeIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.state_store = EditorStateStore()
        self.editor_service = EditorService(self.state_store)
        # On utilise une URL locale pour le test
        self.manager = OpenCodeConnectorManager("ws://127.0.0.1:8000", self.state_store, self.editor_service)
        self.manager.set_editor_update_callback(lambda x: logger.info(f"Callback reçu : {x}"))

    async def asyncTearDown(self):
        if self.manager.client:
            await self.manager.client.close()

    async def test_full_flow(self):
        # 1. Lancer le serveur mock dans un thread séparé
        mock_server = MockOpenCodeServer()
        server_thread = threading.Thread(target=lambda: asyncio.run(mock_server.run()), daemon=True)
        server_thread.start()
        time.sleep(2) # Laisser le temps au serveur de démarrer

        # 2. Connecter le manager
        logger.info("Connexion du manager au Mock Server...")
        await self.manager.start()
        
        # 3. Attendre une mise à jour (le mock envoie toutes les secondes)
        await asyncio.sleep(2)
        
        # 4. Vérifier l'état via le service de domaine
        state = self.editor_service.get_current_state()
        logger.info(f"État récupéré : {state}")
        
        self.assertIsNotNone(state)
        self.assertEqual(state["active_file"]["path"], "/mock/path/file.py")
        
        # 5. Tester l'executor d'action
        executor = ActionExecutor(self.editor_service)
        action = executor.execute_action("insert_code", {"content": "new_code"})
        
        logger.info(f"Action générée : {action}")
        self.assertEqual(action["action"], "insert_code")
        self.assertEqual(action["params"]["content"], "new_code")
        self.assertEqual(action["params"]["line"], 1)
        self.assertEqual(action["params"]["col"], 10)

        # 6. Simuler l'envoi de l'action
        await self.manager.send_action("insert_code", {"content": "new_code"})
        logger.info("Action envoyée avec succès via le manager.")

if __name__ == "__main__":
    unittest.main()
