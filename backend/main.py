import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any

from backend.domain.core.editor_state import InMemoryStateStore
from backend.domain.core.editor_service import EditorService
from backend.domain.core.filesystem_service import FilesystemService
from backend.domain.core.action_executor import ActionExecutor
from backend.application.intelligence.intelligence_service import init_intelligence_service, get_intelligence_service
from backend.application.intelligence.task_planner import get_task_planner
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager
from backend.infrastructure.mcp.server import server as hermes_mcp_server
from backend.transport.websocket_manager import ws_manager

app = FastAPI(title="Hermes Backend API", version="1.0.0")

# --- Initialisation des Services ---

# 1. Stockage d'état
state_store = InMemoryStateStore()

# 2. Services de base
filesystem_service = FilesystemService()
editor_service = EditorService(state_store, filesystem_service)

# 3. Connecteur OpenCode
connector_manager = OpenCodeConnectorManager(editor_service, None)

# 4. Intelligence & Planning
# On initialise le service d'intelligence avec les composants requis
init_intelligence_service(
    get_task_planner(),
    ActionExecutor(editor_service, filesystem_service),
    connector_manager
)

# --- Routes API ---

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/api/editor_state")
async def get_editor_state():
    return editor_service.get_current_state()

# --- Transport WebSocket ---

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(websocket, client_id)
    try:
        while True:
            # On garde la connexion ouverte
            data = await websocket.receive_text()
            # On peut traiter des messages entrants ici si nécessaire
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)

# --- Points d'accès MCP ---

@app.get("/mcp/tools")
async def list_mcp_tools():
    """Expose la liste des outils pour le client MCP."""
    return hermes_mcp_server.list_tools()

@app.post("/mcp/call")
async def call_mcp_tool(request: Dict[str, Any]):
    """Exécute un outil spécifique demandé par le client MCP."""
    tool_name = request.get("tool_name")
    arguments = request.get("arguments", {})
    result = await hermes_mcp_server.call_tool(tool_name, arguments)
    return result

if __name__ == "__main__":
    # Lancement du serveur sur le port 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
