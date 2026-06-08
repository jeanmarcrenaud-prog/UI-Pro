"""
ModelDiscovery - Service unifié de découverte des modèles LLM

Découvre et enrichit les modèles de tous les backends avec:
- Capacités inférées (vision, code, reasoning, creative)
- Contexte max estimé, vitesse, taille paramètres
- État VRAM (modèles chargés en mémoire)
- Cache avec TTL
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from backend.infrastructure.llm.factory import get_backend, list_available_backends

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DiscoveredModel:
    """Représente un modèle découvert sur un backend, avec capacités enrichies."""

    name: str
    backend: str  # "ollama", "llamacpp", "lmstudio", "lemonade"

    # Métadonnées brutes
    size: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    modified_at: str | None = None

    # Capacités inférées
    capabilities: list[str] | None = None  # ["chat", "vision", "code", ...]
    max_context: int = 8192
    speed_tier: str = "medium"  # very_fast, fast, medium, slow

    is_vision: bool = False
    is_coder: bool = False
    is_reasoning: bool = False

    # État VRAM
    is_loaded: bool = False
    size_vram_gb: float | None = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = ["chat"]


# ---------------------------------------------------------------------------
# Enrichissement
# ---------------------------------------------------------------------------


def _estimate_max_context(param_size: str, family: str) -> int:
    """Estime la fenêtre de contexte max selon la taille du modèle."""
    size = param_size.lower()
    if any(x in size for x in ["70b", "72b", "405b"]):
        return 32768
    if "32b" in size:
        return 16384
    if any(x in size for x in ["13b", "14b", "8b", "9b"]):
        return 8192
    # Fallback pour les modèles < 7b
    if any(x in size for x in ["3b", "4b", "2b", "1b"]):
        return 4096
    return 8192


def _estimate_speed(quantization: str | None, param_size: str) -> str:
    """Estime la vitesse selon la quantification et la taille."""
    if isinstance(quantization, dict):
        quantization = quantization.get("level") or quantization.get("name") or ""
    quant = str(quantization or "").upper()
    size = (param_size or "").lower()

    if any(q in quant for q in ["Q2", "Q3", "IQ2", "IQ3"]) or "1b" in size:
        return "very_fast"
    if "Q4" in quant or any(s in size for s in ["7b", "8b"]):
        return "fast"
    if "Q5" in quant or "Q6" in quant:
        return "medium"
    return "slow"


def _infer_capabilities(name: str, family: str | None = None) -> list[str]:
    """Infère les capacités du modèle à partir de son nom et de sa famille."""
    name_lower = name.lower()
    caps: list[str] = ["chat"]

    # Vision
    if any(x in name_lower for x in ["llava", "vision", "moondream", "bakllava"]):
        caps.append("vision")
        caps.append("image")
        caps.append("analysis")

    # Code
    if any(x in name_lower for x in ["coder", "code", "deepseek", "qwen2.5"]):
        caps.append("code")

    # Reasoning
    if any(x in name_lower for x in ["llama", "mistral", "qwen", "deepseek", "opus"]):
        if "reasoning" not in caps:
            caps.append("reasoning")

    # Creative
    if "gemma" in name_lower:
        caps.append("creative")

    # Embeddings
    if "embed" in name_lower:
        caps.append("embeddings")

    # Déduplication en conservant l'ordre
    seen: set[str] = set()
    return [c for c in caps if not (c in seen or seen.add(c))]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TTLCache:
    """Cache simple avec Time-To-Live."""

    def __init__(self, ttl: float = 15.0):
        self._ttl = ttl
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        if key in self._data:
            expires, value = self._data[key]
            if time.monotonic() < expires:
                return value
            del self._data[key]
        return None

    def set(self, key: str, value: Any):
        self._data[key] = (time.monotonic() + self._ttl, value)

    def clear(self):
        self._data.clear()


class ModelDiscovery:
    """Découverte et enrichissement des modèles via les providers LLM."""

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
        # TTL=300s (5 min) — model list is essentially static (only changes on
        # install/uninstall). Sidebar polls every 120s, so the cache always
        # lands on a hit. VRAM state is mutated in-place by
        # _schedule_vram_refresh, so freshness is preserved without
        # invalidating the model list. The 3-4s discovery cost is paid once
        # at startup (lifespan hook) and on force_refresh=True.
        self._cache = TTLCache(ttl=300.0)

    # ── Public API ──────────────────────────────────────────────

    async def discover_all(self, force_refresh: bool = False) -> list[DiscoveredModel]:
        """Découvre les modèles de tous les providers LLM avec capacités enrichies.

        Les résultats sont mis en cache (TTL 300s par défaut).
        Utiliser force_refresh=True pour contourner le cache.

        L'état VRAM (is_loaded, size_vram_gb) est enrichi en arrière-plan
        via un cache séparé rafraîchi en parallèle — la réponse HTTP ne
        reste pas bloquée sur les sondes Lemonade qui peuvent prendre
        plusieurs secondes.
        """
        if not force_refresh:
            cached = self._cache.get("all")
            if cached is not None:
                # Si un rafraîchissement VRAM est terminé, on met à jour
                # les entrées du cache en place.
                vram_cache = self._cache.get("vram")
                if vram_cache:
                    self._apply_vram_state(cached, vram_cache)
                return cached

        backends = list_available_backends()
        tasks = [self._discover_backend(name) for name in backends]

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_models: list[DiscoveredModel] = []
        for result in raw_results:
            if isinstance(result, BaseException):
                logger.warning("Discovery error on one backend: %s", result)
                continue
            all_models.extend(result)

        # Lancer la sonde VRAM en arrière-plan sans bloquer la réponse.
        # La première réponse est livrée immédiatement (is_loaded=None) ;
        # les polls suivants verront le cache VRAM rempli (mutation in-place
        # sur la liste cachée, et entrée "vram" séparée pour les lecteurs
        # tardifs).
        self._schedule_vram_refresh(all_models)

        all_models.sort(key=lambda m: (m.backend, m.name))
        self._cache.set("all", all_models)
        return all_models

    def _schedule_vram_refresh(self, all_models: list[DiscoveredModel]) -> None:
        """Lance la détection VRAM en arrière-plan et met à jour le cache.

        Les sondes peuvent être lentes (3s chacune, parallélisées) ; on
        évite de bloquer la réponse HTTP initiale du /api/models.
        """
        async def _runner() -> None:
            try:
                vram = await self._collect_vram_state(all_models)
                # Mettre à jour le cache principal (référence) si présent
                cached = self._cache.get("all")
                if cached is not None:
                    self._apply_vram_state(cached, vram)
                # Stocker l'état VRAM pour les lectures suivantes
                self._cache.set("vram", vram)
            except Exception as e:
                logger.debug("Background VRAM refresh failed: %s", e)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_runner())
            else:
                loop.run_until_complete(_runner())
        except RuntimeError:
            # Pas de boucle (contexte synchrone) — lancer en thread
            import threading
            def _thread_runner() -> None:
                asyncio.run(_runner())
            threading.Thread(target=_thread_runner, daemon=True).start()

    def _apply_vram_state(
        self,
        models: list[DiscoveredModel],
        vram: dict[tuple[str, str], float | None],
    ) -> None:
        """Applique l'état VRAM chargé sur la liste (en place)."""
        for m in models:
            key = (m.backend, m.name)
            if key in vram:
                m.is_loaded = True
                m.size_vram_gb = vram[key]

    async def _collect_vram_state(
        self, all_models: list[DiscoveredModel]
    ) -> dict[tuple[str, str], float | None]:
        """Collecte l'état VRAM (Ollama + Lemonade) en parallèle."""
        ollama_map, lemonade_map = await asyncio.gather(
            self._get_loaded_ollama_models(),
            self._get_loaded_lemonade_models(
                [m.name for m in all_models if m.backend == "lemonade"]
            ),
        )
        vram: dict[tuple[str, str], float | None] = {}
        for name, size in ollama_map.items():
            vram[("ollama", name)] = size
        for name, size in lemonade_map.items():
            vram[("lemonade", name)] = size
        return vram

    async def get_models_by_backend(self, backend: str) -> list[DiscoveredModel]:
        """Récupère les modèles d'un backend spécifique."""
        all_models = await self.discover_all()
        return [m for m in all_models if m.backend == backend]

    def get_model_names(self) -> list[str]:
        """Récupère tous les noms de modèles (sans découverte)."""
        cached = self._cache.get("all")
        return [m.name for m in cached] if cached else []

    def is_model_available(self, model_name: str) -> bool:
        """Vérifie si un modèle est disponible dans le cache."""
        cached = self._cache.get("all")
        return any(m.name == model_name for m in cached) if cached else False

    def get_backend_for_model(self, model_name: str) -> str | None:
        """Return the backend ("ollama", "lmstudio", ...) that hosts
        `model_name`, or None if the cache is cold or the model is
        unknown.

        Used by the per-node routing layer: when the routing preset
        forces a model from a different backend than the one the user
        originally selected (e.g. user picked an Ollama model, but
        the "fast" tier forces a LM Studio model), the router needs
        to know the right backend to send the request to — otherwise
        it would forward the LM Studio model name to Ollama, which
        404s.

        Synchronous because it only reads the warm cache. If the
        cache is cold (no discovery has run yet), returns None and
        callers must fall back to whatever default they had.
        """
        if not model_name:
            return None
        cached = self._cache.get("all")
        if not cached:
            return None
        for m in cached:
            if m.name == model_name:
                return m.backend
        return None

    # ── Internal ────────────────────────────────────────────────

    async def _discover_backend(self, name: str) -> list[DiscoveredModel]:
        """Découvre et enrichit les modèles d'un backend.

        Timeout de 5s par backend — si list_models est lent
        (ex. Lemonade /v1/models parfois >3s) on ne bloque pas
        tout le /api/models.
        """
        try:
            backend = get_backend(name)
            models = await asyncio.wait_for(
                asyncio.to_thread(backend.list_models),
                timeout=self.timeout * 2,
            )
            return [self._enrich_model(m, name) for m in models]
        except asyncio.TimeoutError:
            logger.warning("%s list_models timed out after %ss", name, self.timeout * 2)
            return []
        except Exception as e:
            logger.debug("%s discovery failed: %s", name, e)
            return []

    def _enrich_model(self, raw: dict, backend: str) -> DiscoveredModel:
        """Enrichit les données brutes du modèle avec capacités inférées."""
        name = raw.get("name", "")
        param_size = raw.get("parameter_size") or ""
        quantization = raw.get("quantization_level")
        family = raw.get("family") or ""

        capabilities = _infer_capabilities(name, family)
        max_context = _estimate_max_context(param_size, family)
        speed_tier = _estimate_speed(quantization, param_size)

        return DiscoveredModel(
            name=name,
            backend=backend,
            size=str(raw.get("size", "")),
            family=family or None,
            parameter_size=param_size or None,
            quantization=str(quantization) if quantization else None,
            modified_at=raw.get("modified_at"),
            capabilities=capabilities,
            max_context=max_context,
            speed_tier=speed_tier,
            is_vision="vision" in capabilities,
            is_coder="code" in capabilities,
            is_reasoning="reasoning" in capabilities,
        )

    async def _get_loaded_ollama_models(self) -> dict[str, float | None]:
        """Récupère les modèles actuellement chargés en VRAM sur Ollama."""
        try:
            import httpx

            backend = get_backend("ollama")
            # config.url est typiquement "http://localhost:11434/api/generate"
            base = backend.config.url.rstrip("/").replace("/api/generate", "")
            url = f"{base}/api/ps"
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            return {
                m.get("name", ""): (
                    round(m.get("size_vram", 0) / (1024**3), 2)
                    if m.get("size_vram")
                    else None
                )
                for m in data.get("models", [])
            }
        except Exception as e:
            logger.debug("Ollama loaded models check failed: %s", e)
            return {}

    async def _get_loaded_lemonade_models(
        self, model_names: list[str]
    ) -> dict[str, float | None]:
        """Détermine les modèles Lemonade chargés en VRAM par sonde légère.

        Envoie une requête minimaliste (max_tokens=1) à chaque modèle
        en parallèle. Si le modèle répond sous 3s, il est considéré chargé.
        """
        if not model_names:
            return {}

        try:
            import asyncio
            import httpx
            from backend.domain.settings import settings

            base_url = settings.lemonade_url.rstrip("/")
            chat_url = f"{base_url}/v1/chat/completions"

            async def _probe(name: str) -> tuple[str, float | None] | None:
                try:
                    start = time.monotonic()
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        resp = await client.post(
                            chat_url,
                            json={
                                "model": name,
                                "messages": [{"role": "user", "content": "hi"}],
                                "max_tokens": 1,
                                "stream": False,
                            },
                        )
                        elapsed = time.monotonic() - start
                        if resp.status_code == 200:
                            return (name, round(elapsed, 2))
                        return None
                except Exception:
                    return None

            results = await asyncio.gather(*[_probe(n) for n in model_names])
            loaded = {}
            for r in results:
                if r is not None:
                    loaded[r[0]] = r[1]
            if loaded:
                logger.info(
                    "Lemonade loaded models (%d/%d): %s",
                    len(loaded),
                    len(model_names),
                    list(loaded.keys()),
                )
            return loaded
        except Exception as e:
            logger.debug("Lemonade loaded models check failed: %s", e)
            return {}

    # ── Health ──────────────────────────────────────────────────

    async def health_check_all(self) -> dict[str, bool]:
        """Vérifie la santé de tous les backends."""
        backends = list_available_backends()
        results: dict[str, bool] = {}

        for name in backends:
            try:
                backend = get_backend(name)
                status = await asyncio.to_thread(backend.health_check)
                results[name] = status.get("status") == "ok"
            except Exception:
                results[name] = False

        return results

    def clear_cache(self):
        """Vide le cache."""
        self._cache.clear()


# ==================== Convenience (compat) ====================


def get_models_summary(all_models: list[DiscoveredModel]) -> list[dict[str, Any]]:
    """Build a summary dict list from discovered models (for API responses)."""
    return [
        {
            "name": m.name,
            "backend": m.backend,
            "size": m.size,
            "family": m.family,
            "parameter_size": m.parameter_size,
            "quantization": m.quantization,
            "speed_tier": m.speed_tier,
            "max_context": m.max_context,
            "capabilities": m.capabilities,
            "is_vision": m.is_vision,
            "is_coder": m.is_coder,
            "is_reasoning": m.is_reasoning,
            "is_loaded": m.is_loaded,
            "size_vram_gb": m.size_vram_gb,
        }
        for m in all_models
    ]


# ==================== Singleton ====================

_discovery_instance: ModelDiscovery | None = None


def get_model_discovery() -> ModelDiscovery:
    """Retourne l'instance singleton de ModelDiscovery."""
    global _discovery_instance
    if _discovery_instance is None:
        _discovery_instance = ModelDiscovery(timeout=3.0)
    return _discovery_instance
