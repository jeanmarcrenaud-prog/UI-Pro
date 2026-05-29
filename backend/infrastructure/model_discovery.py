"""
ModelDiscovery - Service unifié de découverte des modèles LLM
Support complet : Ollama, LM Studio, Lemonade, llama.cpp
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from models.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredModel:
    """Représente un modèle découvert sur un backend."""

    name: str
    backend: str
    size: str | None = None
    family: str | None = None
    context_length: int | None = None
    capabilities: list[str] | None = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = ["chat"]


class ModelDiscovery:
    """Découverte intelligente et mise en cache des modèles disponibles."""

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)
        self._cache: dict[str, list[DiscoveredModel]] = {}

    async def discover_all(self) -> list[DiscoveredModel]:
        """Découvre les modèles sur tous les backends configurés."""
        tasks = [
            self._discover_ollama(),
            self._discover_lmstudio(),
            self._discover_lemonade(),
            self._discover_llamacpp(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_models: list[DiscoveredModel] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Discovery error on one backend: {result}")
                continue
            all_models.extend(result)

        # Tri par backend puis par nom
        all_models.sort(key=lambda m: (m.backend, m.name))
        self._cache["all"] = all_models
        return all_models

    async def _discover_ollama(self) -> list[DiscoveredModel]:
        """Ollama - API native."""
        try:
            url = f"{settings.ollama_url.rstrip('/')}/api/tags"
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()

            models = []
            for m in data.get("models", []):
                details = m.get("details", {})
                models.append(
                    DiscoveredModel(
                        name=m["name"],
                        backend="ollama",
                        size=str(m.get("size", "")),
                        family=details.get("family"),
                        context_length=details.get("context_length"),
                        capabilities=(
                            ["chat", "embeddings"]
                            if "embed" in m["name"].lower()
                            else ["chat"]
                        ),
                    )
                )
            return models
        except Exception as e:
            logger.debug(f"Ollama discovery failed: {e}")
            return []

    async def _discover_lmstudio(self) -> list[DiscoveredModel]:
        """LM Studio - Compatible OpenAI."""
        try:
            url = f"{settings.lmstudio_url.rstrip('/')}/v1/models"
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()

            return [
                DiscoveredModel(
                    name=model.get("id") or model.get("model", "unknown"),
                    backend="lmstudio",
                    capabilities=["chat"],
                )
                for model in data.get("data", [])
            ]
        except Exception as e:
            logger.debug(f"LM Studio discovery failed: {e}")
            return []

    async def _discover_lemonade(self) -> list[DiscoveredModel]:
        """Lemonade backend."""
        try:
            url = f"{settings.lemonade_url.rstrip('/')}/v1/models"
            resp = await self._client.get(url, timeout=2.5)
            resp.raise_for_status()
            data = resp.json()

            return [
                DiscoveredModel(
                    name=model.get("id") or model.get("model", "unknown"),
                    backend="lemonade",
                    capabilities=["chat"],
                )
                for model in data.get("data", [])
            ]
        except Exception as e:
            logger.debug(f"Lemonade discovery failed: {e}")
            return []

    async def _discover_llamacpp(self) -> list[DiscoveredModel]:
        """llama.cpp server (llama-server)."""
        try:
            url = f"{settings.llamacpp_url.rstrip('/')}/v1/models"
            resp = await self._client.get(url, timeout=2.5)
            resp.raise_for_status()
            data = resp.json()

            return [
                DiscoveredModel(
                    name=model.get("id") or model.get("model", "unknown"),
                    backend="llamacpp",
                    capabilities=["chat"],
                )
                for model in data.get("data", [])
            ]
        except Exception as e:
            logger.debug(f"llama.cpp discovery failed: {e}")
            return []

    async def get_models_by_backend(self, backend: str) -> list[DiscoveredModel]:
        """Récupère uniquement les modèles d'un backend spécifique."""
        if "all" not in self._cache:
            await self.discover_all()
        return [m for m in self._cache["all"] if m.backend == backend]

    async def health_check_all(self) -> dict[str, bool]:
        """Vérifie la santé de tous les backends."""
        backends = {
            "ollama": settings.ollama_url,
            "lmstudio": getattr(settings, "lmstudio_url", None),
            "lemonade": getattr(settings, "lemonade_url", None),
            "llamacpp": getattr(settings, "llamacpp_url", None),
        }

        results = {}
        for name, base_url in backends.items():
            if not base_url:
                results[name] = False
                continue

            try:
                if name == "ollama":
                    url = f"{base_url.rstrip('/')}/api/tags"
                else:
                    url = f"{base_url.rstrip('/')}/v1/models"

                resp = await self._client.get(url, timeout=2.0)
                results[name] = resp.status_code < 400
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
            "capabilities": m.capabilities,
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
