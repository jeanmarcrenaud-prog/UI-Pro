# api/routers/chat.py - Chat endpoint (REST fallback)
import json
import logging
import re
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.domain.settings import settings
from backend.transport.deps import verify_api_key

router = APIRouter(prefix="/api", tags=["chat"])

logger = logging.getLogger(__name__)


def _default_model_for(models: list[dict], provider: str) -> str:
    """Repère un modèle textuel dispo chez le provider (premier non-embedding)."""
    for m in models:
        name = (m.get("name") or m.get("id") or "")
        if not name:
            continue
        if "embed" in name.lower():
            continue
        return name
    return next((m.get("name") or m.get("id") or "" for m in models), "")


def _resolve_provider(model: str, provider: str) -> tuple[str, str]:
    """Local-first : si le provider demandé n'a pas de modèle dispo, bascule
    automatiquement sur un autre backend (LM Studio / Ollama) qui en a.

    Retourne ``(model, provider)`` réellement exploitables.
    """
    candidates = [provider] + [p for p in ("ollama", "lmstudio") if p != provider]
    for prov in candidates:
        try:
            from backend.infrastructure.llm import factory as _factory

            backend = _factory.get_backend(prov)
        except Exception:  # backend non enregistré
            continue
        try:
            models = backend.list_models()
        except Exception:  # provider hors ligne
            continue
        if not models:
            continue
        # 1) si le modèle demandé est dispo chez ce provider -> on l'utilise
        for m in models:
            name = (m.get("name") or m.get("id") or "")
            if model and model.lower() in name.lower():
                return name, prov
        # 2) sinon un modèle de repli adapté au provider
        fallback = _default_model_for(models, prov)
        if fallback:
            return fallback, prov
    return model, provider

class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    provider: str | None = None  # ollama, lmstudio, lemonade, llamacpp


class ChatResponse(BaseModel):
    result: str
    status: str = "success"


@router.post("/chat", dependencies=[Depends(verify_api_key)])
async def chat(request: ChatRequest):
    """Chat endpoint (REST fallback when WebSocket fails)"""
    try:
        logger.debug(
            f"[CHAT] Request: message={request.message[:50]}... model={request.model} provider={request.provider}"
        )

        from backend.infrastructure.streaming import stream_chat

        # Local-first : si le provider demandé n'a pas de modèle dispo (ex Ollama
        # sans modèle), on bascule automatiquement sur un autre backend (LM Studio).
        resolved_model, resolved_provider = _resolve_provider(
            request.model or settings.model_fast,
            request.provider or "ollama",
        )
        logger.info(f"[CHAT] Resolved provider/model: {resolved_provider}/{resolved_model}")

        # Collect full response from streaming (async)
        chunks = []
        async for chunk in stream_chat(
            prompt=request.message,
            model=resolved_model,
            provider=resolved_provider,
        ):
            if chunk.text:
                chunks.append(chunk.text)

        result_text = "".join(chunks)
        logger.info(f"[CHAT] Response generated: {len(result_text)} characters")
        return ChatResponse(result=result_text, status="success")

    except Exception as e:
        logger.error(f"[CHAT] Error: {type(e).__name__}: {e!s}")
        return ChatResponse(result=f"Error: {e!s}", status="error")


@router.post("/stream", dependencies=[Depends(verify_api_key)])
async def stream(request: ChatRequest):
    """SSE streaming endpoint (fallback when WebSocket fails)"""

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            logger.debug(
                f"[STREAM] Starting stream: message={request.message[:50]}... model={request.model}"
            )

            from backend.infrastructure.streaming import stream_chat

            chunk_count = 0
            async for chunk in stream_chat(
                prompt=request.message,
                model=request.model or settings.model_fast,
                provider=request.provider or "ollama",
            ):
                if chunk.text:
                    chunk_count += 1
                    yield f"data: {{'content': '{chunk.text.replace(chr(10), ' ')}', 'done': false}}\n\n"

            logger.info(f"[STREAM] Completed: {chunk_count} chunks sent")
            yield "data: {'done': true}\n\n"
        except Exception as e:
            logger.error(f"[STREAM] Error: {type(e).__name__}: {e!s}")
            yield f"data: {{'error': '{e!s}', 'done': true}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─── Chat simple (sans pipeline LangGraph) ─────────────────────────────
# Le mobile a besoin d'un vrai chat : /api/stream (agent pipeline) est inadapté
# pour une conversation (analyse → plan → code → revue → exécution). Ici on
# streame directement les tokens du backend LLM sélectionné.

_TEXT_PROVIDERS = ("ollama", "lmstudio", "lemonade", "llamacpp")
_DEFAULT_SYSTEM = (
    "Tu es UI Pro, un assistant utile et concis. Réponds en français sauf "
    "demande contraire. Utilise des blocs de code Markdown quand c'est pertinent."
)


class PlainMessage(BaseModel):
    role: str = "user"
    content: str


class PlainChatRequest(BaseModel):
    message: str
    model: str | None = None
    provider: str | None = None
    history: list[PlainMessage] = []
    temperature: float = 0.7
    system: str | None = None


def _list_text_models(provider: str) -> list[str]:
    """Noms de modèles textuels joignables pour ce provider (embedding exclus)."""
    try:
        from backend.infrastructure.llm import factory

        backend = factory.get_backend(provider)
        models = backend.list_models()
    except Exception:
        return []
    names: list[str] = []
    for m in models:
        name = (m.get("name") or m.get("id") or "") if isinstance(m, dict) else ""
        if name and "embed" not in name.lower():
            names.append(name)
    return names


def _param_size(name: str) -> float:
    """Taille approximative en milliards de paramètres, déduite du nom."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", name.lower())
    return float(m.group(1)) if m else 999.0


def _resolve_plain_model(model: str | None, provider: str | None) -> tuple[str, str]:
    """Choisit un couple (modèle, provider) réellement disponible.

    Priorité : modèle demandé → `settings.model_fast` → plus petit modèle du
    provider demandé → plus petit modèle des autres providers. Évite le piège
    d'un `model_fast` configuré mais absent (ex. « liquid/lfm2.5-1.2b »).
    """
    preferred = [m for m in (model, settings.model_fast) if m]
    providers: list[str] = []
    if provider:
        providers.append(provider)
    providers += [p for p in _TEXT_PROVIDERS if p not in providers]

    available: dict[str, list[str]] = {}
    for p in providers:
        names = _list_text_models(p)
        if names:
            available[p] = names

    if not available:  # aucun backend joignable : l'appel échouera explicitement
        return (model or settings.model_fast or ""), (provider or "ollama")

    # 1) correspondance avec un nom préféré
    for want in preferred:
        low = want.lower()
        for p, names in available.items():
            for n in names:
                if low == n.lower() or low in n.lower():
                    return n, p

    # 2) repli : plus petit modèle du premier provider disponible
    p = next(iter(available))
    names = sorted(available[p], key=_param_size)
    logger.warning(
        "[CHAT/STREAM] Modèle configuré introuvable (%s) — repli sur %s/%s",
        settings.model_fast,
        p,
        names[0],
    )
    return names[0], p


def _build_plain_prompt(request: PlainChatRequest) -> str:
    """Convertit l'historique en prompt texte (compatible /api/generate)."""
    turns: list[str] = []
    for m in request.history[-12:]:
        if not m.content.strip():
            continue
        turns.append(f"{'User' if m.role == 'user' else 'Assistant'}: {m.content.strip()}")
    turns.append(f"User: {request.message.strip()}")
    turns.append("Assistant:")
    return "\n\n".join(turns)


@router.post("/chat/stream", dependencies=[Depends(verify_api_key)])
async def chat_stream_plain(request: PlainChatRequest):
    """Streaming token-par-token d'un chat simple (sans orchestrateur).

    Réponse SSE : `data: {"content": "...", "done": false}` puis
    `data: {"done": true, "model": ..., "provider": ...}`.
    Les en-têtes `X-Model` / `X-Provider` indiquent le modèle réellement utilisé.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    model, provider = _resolve_plain_model(request.model, request.provider)
    logger.info("[CHAT/STREAM] %s/%s", provider, model)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            from backend.infrastructure.llm import factory

            backend = factory.get_backend(provider)
            backend.config.model = model
            prompt = _build_plain_prompt(request)
            async for token in backend.astream(
                prompt,
                temperature=request.temperature,
                system_prompt=request.system or _DEFAULT_SYSTEM,
            ):
                if isinstance(token, str) and token:
                    payload = json.dumps({"content": token, "done": False}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
            done = json.dumps({"done": True, "model": model, "provider": provider}, ensure_ascii=False)
            yield f"data: {done}\n\n"
        except Exception as e:
            logger.exception("[CHAT/STREAM] Error")
            payload = json.dumps({"error": f"{type(e).__name__}: {e}", "done": True}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    response = StreamingResponse(event_generator(), media_type="text/event-stream")
    response.headers["X-Model"] = model
    response.headers["X-Provider"] = provider
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response