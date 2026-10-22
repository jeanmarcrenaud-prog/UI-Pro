# api/routers/mcp.py - MCP (Model Context Protocol) Router
# Hermes MCP server endpoints exposed via FastAPI

from fastapi import APIRouter, Body
from typing import Dict, Any, Optional

router = APIRouter(
    prefix="/api/mcp",
    tags=["MCP"],
)

# ─── Dependencies ────────────────────────────────────

def _get_server() -> "HermesMCPServer":
    """Lazy getter for Hermes MCP server instance."""
    from backend.infrastructure.mcp.server import get_server
    return get_server()


# ─── MCP: Execute Intent ─────────────────────────────

@router.post("/execute-intent")
async def mcp_execute_intent(
    intent: str = Body(..., description="L'intention de l'utilisateur"),
    context: Optional[str] = Body(None, description="Contexte additionnel (optionnel)"),
) -> Dict[str, Any]:
    """Execute user intent via the Hermes MCP server."""
    server = _get_server()
    result = await server.intelligence_service.process_user_intent(
        intent, server.state_store.get_state()
    )
    return {"success": True, "content": str(result)}


# ─── MCP: Read File ──────────────────────────────────

@router.post("/read-file")
async def mcp_read_file(
    path: str = Body(..., description="Chemin relatif du fichier à lire"),
) -> Dict[str, Any]:
    """Read a file via the Hermes MCP server."""
    server = _get_server()
    file_data = server.filesystem_service.read_file(path)
    if file_data:
        return {"success": True, "content": file_data.content}
    return {"success": False, "content": f"Erreur : Fichier {path} non trouvé."}


# ─── MCP: Write File ─────────────────────────────────

@router.post("/write-file")
async def mcp_write_file(
    path: str = Body(..., description="Chemin du fichier à créer/écrire"),
    content: str = Body(..., description="Contenu à écrire dans le fichier"),
) -> Dict[str, Any]:
    """Write a file via the Hermes MCP server."""
    server = _get_server()
    success = server.filesystem_service.write_file(path, content)
    return {"success": success, "content": "Succès" if success else "Échec de l'écriture."}


# ─── MCP: Chat ───────────────────────────────────────

@router.post("/chat")
async def mcp_chat(
    message: str = Body(..., description="Message utilisateur"),
    session_id: Optional[str] = Body(None, description="ID de session existant (optionnel)"),
) -> Dict[str, Any]:
    """Chat directly with Hermes via the MCP server."""
    server = _get_server()
    result = await server._handle_chat(message, session_id)
    return {"success": True, "content": result.get("content", ""), "session_id": result.get("session_id")}


# ─── MCP: Health ───────────────────────────────────────

@router.get("/health")
async def mcp_health() -> Dict[str, Any]:
    """Check MCP server health."""
    from backend.infrastructure.mcp.server import get_server_state
    state = get_server_state()
    return {"initialized": state.get("initialized", False), "llm_client_ready": state.get("llm_client_ready", False)}