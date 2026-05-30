"""
ModelDiscovery - Service unifié de découverte des modèles LLM

Refactored to delegate to the provider implementations (get_backend().list_models())
instead of duplicating endpoint URLs.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from backend.infrastructure.llm.factory import get_backend, list_available_backends

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ModelDiscovery:
    """Découverte et mise en cache des modèles via les providers LLM."""

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)
        self._cache: dict[str, list[DiscoveredModel]] = {}

    # ── Public API ──────────────────────────────────────────────

    async def discover_all(self) -> list[DiscoveredModel]:
        """Découvre les modèles sur tous les backends enregistrés."""
        backends = list_available_backends()
        tasks = [self._discover_backend(name) for name in backends]

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_models: list[DiscoveredModel] = []
        for result in raw_results:
            if isinstance(result, BaseException):
                logger.warning(f"Discovery error on one backend: {result}")
                continue
            all_models.extend(result)

        all_models.sort(key=lambda m: (m.backend, m.name))
        self._cache["all"] = all_models
        return all_models

    async def get_models_by_backend(self, backend: str) -> list[DiscoveredModel]:
        """Récupère uniquement les modèles d'un backend spécifique."""
        if "all" not in self._cache:
            await self.discover_all()
        return [m for m in self._cache["all"] if m.backend == backend]

    # ── Internal ────────────────────────────────────────────────

    async def _discover_backend(self, name: str) -> list[DiscoveredModel]:
        """Découvre les modèles d'un backend via son provider."""
        try:
            backend = get_backend(name)
            models = await asyncio.to_thread(backend.list_models)
            return [
                DiscoveredModel(
                    name=m["name"],
                    backend=name,
                    size=str(m.get("size", "")),
                    family=m.get("family"),
                    capabilities=(
                        ["chat", "embeddings"]
                        if "embed" in m["name"].lower()
                        else ["chat"]
                    ),
                )
                for m in models
            ]
        except Exception as e:
            logger.debug(f"{name} discovery failed: {e}")
            return []

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
