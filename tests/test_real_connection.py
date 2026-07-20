import asyncio
import logging
import sys
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.editor_service import EditorService
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # On utilise le port par défaut 8765
    uri = "ws://localhost:8765"
    logger.info(f"Tentative de connexion à {uri}...")
    
    state_store = EditorStateStore()
    editor_service = EditorService(state_store)
    
    # Initialisation du manager avec le store et le service
    manager = OpenCodeConnectorManager(
        uri=uri,
        state_store=state_store,
        editor_service=editor_service
    )
    
    # On définit le callback pour voir les retours
    manager.set_editor_update_callback(lambda x: logger.info(f"Update reçue : {x}"))
    
    try:
        await manager.start()
        logger.info("Connexion établie. Envoi de l'action 'Hello'...")
        
        # Envoi d'une action d'insertion de code
        # On utilise le format attendu par l'ActionExecutor
        await manager.send_action("insert_code", {"content": "Hello from Hermes!"})
        
        # Attente un peu pour laisser le temps au réseau de répondre
        await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"Erreur lors de la communication : {e}")
    finally:
        await manager.stop()

if __name__ == "__main__":
    asyncio.run(main())
