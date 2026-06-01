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
        self._cache = TTLCache(ttl=15.0)

    # ── Public API ──────────────────────────────────────────────

    async def discover_all(self, force_refresh: bool = False) -> list[DiscoveredModel]:
        """Découvre les modèles de tous les backends avec capacités enrichies.

        Les résultats sont mis en cache (TTL 15s par défaut).
        Utiliser force_refresh=True pour contourner le cache.
        """
        if not force_refresh:
            cached = self._cache.get("all")
            if cached is not None:
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

        # Compléter avec l'état VRAM (Ollama)
        loaded_map = await self._get_loaded_ollama_models()
        for model in all_models:
            if model.backend == "ollama" and model.name in loaded_map:
                model.is_loaded = True
                model.size_vram_gb = loaded_map[model.name]

        # Compléter avec l'état VRAM (Lemonade) par sonde légère
        lemonade_models = [m.name for m in all_models if m.backend == "lemonade"]
        if lemonade_models:
            loaded_lemonade = await self._get_loaded_lemonade_models(lemonade_models)
            for model in all_models:
                if model.backend == "lemonade" and model.name in loaded_lemonade:
                    model.is_loaded = True
                    model.size_vram_gb = loaded_lemonade[model.name]

        all_models.sort(key=lambda m: (m.backend, m.name))
        self._cache.set("all", all_models)
        return all_models

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

    # ── Internal ────────────────────────────────────────────────

    async def _discover_backend(self, name: str) -> list[DiscoveredModel]:
        """Découvre et enrichit les modèles d'un backend."""
        try:
            backend = get_backend(name)
            models = await asyncio.to_thread(backend.list_models)
            return [self._enrich_model(m, name) for m in models]
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
            from models.settings import settings

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
