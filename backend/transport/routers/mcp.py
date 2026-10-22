#HM|# api/routers/mcp.py - MCP (Model Context Protocol) Router
#VB|# Hermes MCP server endpoints exposed via FastAPI
#WW|
#TN|from fastapi import APIRouter, Body
#XW|from typing import Dict, Any, Optional
#QH|
#TN|router = APIRouter(
#TN|    prefix="/api/mcp",
#TN|    tags=["MCP"],
#TN|)
#XW|
#TN|# ─── Dependencies ────────────────────────────────────
#TN|
#TN|def _get_server() -> "HermesMCPServer":
#TN|    """Lazy getter for Hermes MCP server instance."""
#TN|    from backend.infrastructure.mcp.server import get_server
#TN|    return get_server()
#TN|
#TN|
#TN|# ─── MCP: Execute Intent ─────────────────────────────
#TN|
#TN|@router.post("/execute-intent")
#TN|async def mcp_execute_intent(
#TN|    intent: str = Body(..., description="L'intention de l'utilisateur"),
#TN|    context: Optional[str] = Body(None, description="Contexte additionnel (optionnel)"),
#TN|) -> Dict[str, Any]:
#TN|    """Execute user intent via the Hermes MCP server."""
#TN|    server = _get_server()
#TN|    result = await server.intelligence_service.process_user_intent(
#TN|        intent, server.state_store.get_state()
#TN|    )
#TN|    return {"success": True, "content": str(result)}
#TN|
#TN|
#TN|# ─── MCP: Read File ──────────────────────────────────
#TN|
#TN|@router.post("/read-file")
#TN|async def mcp_read_file(
#TN|    path: str = Body(..., description="Chemin relatif du fichier à lire"),
#TN|) -> Dict[str, Any]:
#TN|    """Read a file via the Hermes MCP server."""
#TN|    server = _get_server()
#TN|    file_data = server.filesystem_service.read_file(path)
#TN|    if file_data:
#TN|        return {"success": True, "content": file_data.content}
#TN|    return {"success": False, "content": f"Erreur : Fichier {path} non trouvé."}
#TN|
#TN|
#TN|# ─── MCP: Write File ─────────────────────────────────
#TN|
#TN|@router.post("/write-file")
#TN|async def mcp_write_file(
#TN|    path: str = Body(..., description="Chemin du fichier à créer/écrire"),
#TN|    content: str = Body(..., description="Contenu à écrire dans le fichier"),
#TN|) -> Dict[str, Any]:
#TN|    """Write a file via the Hermes MCP server."""
#TN|    server = _get_server()
#TN|    success = server.filesystem_service.write_file(path, content)
#TN|    return {"success": success, "content": "Succès" if success else "Échec de l'écriture."}
#TN|
#TN|
#TN|# ─── MCP: Chat ───────────────────────────────────────
#TN|
#TN|@router.post("/chat")
#TN|async def mcp_chat(
#TN|    message: str = Body(..., description="Message utilisateur"),
#TN|    session_id: Optional[str] = Body(None, description="ID de session existant (optionnel)"),
#TN|) -> Dict[str, Any]:
#TN|    """Chat directly with Hermes via the MCP server."""
#TN|    server = _get_server()
#TN|    result = await server._handle_chat(message, session_id)
#TN|    return {"success": True, "content": result.get("content", ""), "session_id": result.get("session_id")}
#TN|
#TN|
#TN|# ─── MCP: Health ───────────────────────────────────────
#TN|
#TN|@router.get("/health")
#TN|async def mcp_health() -> Dict[str, Any]:
#TN|    """Check MCP server health."""
#TN|    from backend.infrastructure.mcp.server import get_server_state
#TN|    state = get_server_state()
#TN|    return {"initialized": state.get("initialized", False), "llm_client_ready": state.get("llm_client_ready", False)}