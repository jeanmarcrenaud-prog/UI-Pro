import asyncio
import logging
import sys
import os

# Ajouter le répertoire racine au PYTHONPATH
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/../.."))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.application.intelligence.intelligence_service import init_intelligence_service, get_intelligence_service
from backend.domain.core.models import EditorState, Cursor
from backend.domain.core.action_executor import ActionExecutor
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

async def main():
    try:
        # Initialisation des dépendances
        # On tente de récupérer les instances globales.
        # Si elles n'existent pas, on les initialise avec des mocks pour la démonstration.
        try:
            service = get_intelligence_service()
        except RuntimeError:
            logger.info("Le service d'intelligence n'est pas initialisé. Création d'une instance de test.")
            # Simulation minimale pour que le script tourne
            # On injecte un mock du connecteur pour ne pas bloquer sur la connexion réseau
            mock_connector = MagicMock(spec=OpenCodeConnectorManager)
            mock_connector.send_task = AsyncMock(return_value=True)
            init_intelligence_service(MagicMock(), MagicMock(), mock_connector)
            service = get_intelligence_service()

        state = EditorState(cursor=Cursor(line=1, column=1))
        
        print("Envoi de la commande 'bonjour' via l'intelligence...")
        actions = await service.process_voice_command("bonjour", state)
        
        for action in actions:
            print(f"Action générée : {action.action_type} | Status : {action.status}")
            
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de la commande : {e}")

if __name__ == "__main__":
    import unittest.mock
    from unittest.mock import MagicMock
    asyncio.run(main())
