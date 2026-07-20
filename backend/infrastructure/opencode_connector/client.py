import asyncio
import json
import logging
import websockets
from typing import Callable, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from .models import EditorUpdate, HermesAction, OpenCodeResponse

logger = logging.getLogger(__name__)

class OpenCodeClient:
    """
    Client WebSocket pour la communication bidirectionnelle avec le connecteur OpenCode.
    """
    def __init__(self, uri: str, on_update: Callable[[EditorUpdate], None]):
        self.uri = uri
        self.on_update = on_update
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.uri)
            logger.info(f"Connecté au connecteur OpenCode à : {self.uri}")
            asyncio.create_task(self._listen())
        except Exception as e:
            logger.error(f"Échec de la connexion à OpenCode: {e}")

    async def _listen(self):
        try:
            async for message in self.websocket:
                data = json.loads(message)
                
                if "editor_update" in data:
                    update = EditorUpdate(**data["editor_update"])
                    self.on_update(update)
                elif "opencode_response" in data:
                    response = OpenCodeResponse(**data["opencode_response"])
                    logger.debug(f"Réponse reçue : {response.status}")
                else:
                    logger.debug(f"Message inconnu reçu : {data}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connexion WebSocket fermée.")
        except Exception as e:
            logger.error(f"Erreur dans la boucle d'écoute : {e}")

    async def send_action(self, action: HermesAction):
        if self.websocket and self.websocket.open:
            await self.websocket.send(json.dumps({
                "hermes_action": action.dict()
            }))
        else:
            logger.error("Impossible d'envoyer une action : WebSocket non connecté.")

    async def close(self):
        if self.websocket:
            await self.websocket.close()
