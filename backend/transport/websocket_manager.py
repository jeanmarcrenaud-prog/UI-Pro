import asyncio
import logging
import json
from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Hub central pour la diffusion des messages en temps réel vers le frontend (UI-Pro)
    et l'extension OpenCode.
    """
    def __init__(self):
        # Mapping des clients actifs par ID de session
        self.active_connections: Dict[str, WebSocket] = {}
        # Mapping des salons par type d'événement (ex: 'logs', 'actions', 'editor_updates')
        self.channels: Dict[str, Set[str]] = {
            "logs": set(),
            "actions": set(),
            "editor_updates": set()
        }

    async def connect(self, websocket: WebSocket, client_id: str):
        """Établit une connexion et inscrit le client aux salons par défaut."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
        # Inscription par défaut aux salons principaux
        for channel in self.channels.keys():
            self.channels[channel].add(client_id)
        
        logger.info(f"Client connecté : {client_id}")

    def disconnect(self, client_id: str):
        """Supprime le client des connexions et des salons."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        for channel in self.channels.values():
            channel.discard(client_id)
        logger.info(f"Client déconnecté : {client_id}")

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Diffuse un message à tous les clients inscrits à un salon."""
        if channel not in self.channels:
            logger.warning(f"Salon {channel} inconnu.")
            return

        payload = json.dumps(message)
        target_ids = self.channels[channel]
        
        for client_id in target_ids:
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_text(payload)
                except Exception as e:
                    logger.error(f"Erreur d'envoi à {client_id}: {e}")

    async def send_personal_message(self, client_id: str, message: Dict[str, Any]):
        """Envoie un message spécifique à un seul client."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Erreur d'envoi personnel à {client_id}: {e}")

# Instance globale du transport
ws_manager = WebSocketManager()
