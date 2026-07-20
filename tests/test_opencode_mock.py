import asyncio
import json
import logging
import websockets
from typing import List
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager
from backend.infrastructure.opencode_connector.models import EditorUpdate, HermesAction

# Configuration du logging pour voir les échanges
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- MOCK SERVER ---
async def mock_opencode_server(uri: str):
    """Simule un serveur OpenCode qui envoie des updates et reçoit des actions."""
    async def handler(websocket):
        logger.info(f"Serveur Mock : Connexion reçue sur {uri}")
        try:
            # 1. Attendre une action de Hermes
            message = await websocket.recv()
            data = json.loads(message)
            if "hermes_action" in data:
                action = data["hermes_action"]
                logger.info(f"Serveur Mock : Action reçue -> {action['action']} avec {action['params']}")

            # 2. Envoyer une mise à jour de l'éditeur simulée
            mock_update = {
                "editor_update": {
                    "active_file": {
                        "path": "C:/projects/test.py",
                        "content": "print('hello world')"
                    },
                    "cursor": {
                        "line": 1,
                        "column": 12
                    },
                    "diagnostics": [
                        {
                            "severity": "Error",
                            "message": "Undefined variable 'x'",
                            "line": 2,
                            "col": 5
                        }
                    ]
                }
            }
            await websocket.send(json.dumps(mock_update))
            logger.info("Serveur Mock : Update envoyé.")
            
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Serveur Mock Erreur : {e}")

    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.sleep(1) # Laisser le temps au serveur de démarrer

# --- TEST SUITE ---
async def test_opencode_connector_flow():
    uri = "ws://localhost:8765"
    received_updates: List[EditorUpdate] = []

    def on_update_callback(update: EditorUpdate):
        received_updates.append(update)
        logger.info(f"Client : Update reçu -> {update.active_file.path if update.active_file else 'No file'}")

    # Démarrer le serveur mock en tâche de fond
    server_task = asyncio.create_task(mock_opencode_server(uri))
    await asyncio.sleep(1) # Attendre la démarrage du serveur

    # Initialiser le manager
    manager = OpenCodeConnectorManager(uri)
    manager.set_editor_update_callback(on_update_callback)
    
    # Connecter le client
    await manager.start()
    await asyncio.sleep(1) # Attendre la connexion

    # Envoyer une action
    action = HermesAction(action="insert_code", params={"content": "test_code", "line": 1})
    await manager.send_action("insert_code", action.params)

    # Attendre que le mock traite et réponde
    await asyncio.sleep(2)

    # Assertions
    if len(received_updates) > 0:
        assert received_updates[0].active_file.path == "C:/projects/test.py"
        assert received_updates[0].diagnostics[0].severity == "Error"
        logger.info("✅ TEST RÉUSSI : Le flux bidirectionnel est valide.")
    else:
        logger.error("❌ TEST ÉCHOUÉ : Aucune mise à jour reçue du serveur mock.")
    
    await manager.stop()
    server_task.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(test_opencode_connector_flow())
    except Exception as e:
        logger.error(f"Erreur lors du test : {e}")
        exit(1)
