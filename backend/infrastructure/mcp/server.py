import logging
import json
from typing import List, Dict, Any, Optional
from backend.domain.core.models import EditorState as EditorStateModel
from backend.domain.core.editor_service import EditorService
from backend.domain.core.editor_state import EditorStateStore
from backend.domain.core.filesystem_service import FilesystemService
from backend.application.intelligence.intelligence_service import init_intelligence_service, get_intelligence_service
from backend.application.intelligence.task_planner import get_task_planner
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

logger = logging.getLogger(__name__)

class HermesMCPServer:
    """
    Serveur MCP (Model Context Protocol) pour Hermes.
    Expose les capacités de planification, d'exécution et de gestion de fichiers
    sous forme d'outils et de ressources standardisés.
    """
    def __init__(self):
        # Initialisation des services de base
        self.filesystem_service = FilesystemService()
        self.state_store = EditorStateStore()
        self.editor_service = EditorService(self.state_store, self.filesystem_service)
        
        # Initialisation du connecteur OpenCode
        # Pour l'instant, on utilise un mock du client pour le serveur MCP
        self.connector_manager = OpenCodeConnectorManager()
        
        # Initialisation de l'intelligence
        init_intelligence_service(
            get_task_planner(),
            None, # Executor (sera injecté ou utilisé via les outils)
            self.connector_manager
        )
        self.intelligence_service = get_intelligence_service()

    def list_tools(self) -> List[Dict[str, Any]]:
        """Liste tous les outils disponibles pour le client MCP."""
        return [
            {
                "name": "execute_intent",
                "description": "Analyse une intention utilisateur et exécute une série d'actions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string", "description": "L'intention de l'utilisateur (ex: 'crée un fichier python')."},
                        "context": {"type": "string", "description": "Contexte additionnel (optionnel)."}
                    },
                    "required": ["intent"]
                }
            },
            {
                "name": "get_opencode_status",
                "description": "Récupère le statut et les dernières actions d'OpenCode.",
                "input_schema": {"type": "object", "properties": {}}
            },
            {
                "name": "read_file",
                "description": "Lit le contenu d'un fichier spécifique.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Chemin relatif du fichier."}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Écrit ou crée un fichier.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Chemin relatif du fichier."},
                        "content": {"type": "string", "description": "Contenu à écrire."}
                    },
                    "required": ["path", "content"]
                }
            }
        ]

    def list_resources(self) -> List[Dict[str, Any]]:
        """Liste les ressources disponibles (données statiques ou dynamiques)."""
        return [
            {
                "uri": "hermes://editor_state",
                "name": "Editor State",
                "description": "L'état actuel de l'éditeur (curseur, fichiers actifs, etc.)."
            },
            {
                "uri": "hermes://project_context",
                "name": "Project Context",
                "description": "Vue d'ensemble des fichiers et structure du projet."
            }
        ]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute l'outil demandé par le client MCP."""
        if tool_name == "execute_intent":
            stored = self.state_store.get_state()
            state = EditorStateModel(
                cursor=stored.cursor,
                selection=stored.selection,
                active_file=stored.active_file,
                diagnostics=stored.diagnostics,
                terminal_output=stored.terminal_output,
                git_status=stored.git_status,
            )
            actions = await self.intelligence_service.process_user_intent(
                arguments.get("intent", ""), state
            )
            return {"content": f"Actions g\u00e9n\u00e9r\u00e9es : {actions}"}
        
        elif tool_name == "get_opencode_status":
            status = await self.intelligence_service.get_opencode_status()
            return {"content": status}
        
        elif tool_name == "read_file":
            path = arguments.get("path", "")
            file_data = self.filesystem_service.read_file(path)
            if file_data:
                return {"content": file_data.content}
            return {"content": f"Erreur : Fichier {path} non trouvé."}
            
        elif tool_name == "write_file":
            path = arguments.get("path", "")
            content = arguments.get("content", "")
            success = self.filesystem_service.write_file(path, content)
            return {"content": "Succès" if success else "Échec de l'écriture."}
        
        return {"content": f"Erreur : Outil {tool_name} non trouvé."}

# Instance globale du serveur
server = HermesMCPServer()
