import asyncio
import logging
from typing import Optional
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.editor_service import EditorService
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

logger = logging.getLogger(__name__)

# Global instances
_editor_state_store: Optional[EditorStateStore] = None
_editor_service: Optional[EditorService] = None
_opencode_manager: Optional[OpenCodeConnectorManager] = None

def get_editor_service() -> EditorService:
    """Get the singleton EditorService instance."""
    global _editor_service
    if _editor_service is None:
        raise RuntimeError("EditorService is not initialized. Call 'init_editor_services' first.")
    return _editor_service

def get_opencode_manager() -> OpenCodeConnectorManager:
    """Get the singleton OpenCodeConnectorManager instance."""
    global _opencode_manager
    if _opencode_manager is None:
        raise RuntimeError("OpenCodeConnectorManager is not initialized. Call 'init_editor_services' first.")
    return _opencode_manager

async def init_editor_services(ws_uri: str = "ws://localhost:8765"):
    """
    Initialise tous les composants liés à l'état de l'éditeur.
    À appeler au démarrage de l'application (ex: dans le module principal).
    """
    global _editor_state_store, _editor_service, _opencode_manager

    if _editor_state_store is None:
        logger.info("Initialisation du store d'état de l'éditeur...")
        _editor_state_store = EditorStateStore()
    
    if _editor_service is None:
        logger.info("Initialisation du service de domaine de l'éditeur...")
        _editor_service = EditorService(_editor_state_store)
    
    if _opencode_manager is None:
        logger.info(f"Initialisation du connecteur OpenCode sur {ws_uri}...")
        # Correction : On passe bien le state_store et l'editor_service ici
        _opencode_manager = OpenCodeConnectorManager(
            ws_uri, 
            _editor_state_store, 
            _editor_service
        )
        
        # Enregistrer le callback pour mettre à jour le store automatiquement
        _opencode_manager.set_editor_update_callback(
            lambda update: _editor_state_store.update(
                active_file=update.active_file,
                cursor=update.cursor,
                selection=update.selection,
                diagnostics=update.diagnostics,
                terminal_output=update.terminal.get("output") if update.terminal else None,
                git_status=update.git
            )
        )
        
        # Démarrer la connexion (non bloquant)
        asyncio.create_task(_opencode_manager.start())
    
    logger.info("Tous les services de l'éditeur sont initialisés.")
