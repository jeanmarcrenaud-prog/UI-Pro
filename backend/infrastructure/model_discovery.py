# backend/infrastructure/model_discovery.py - Dynamic Multi-Backend Model Discovery
#
# Discovers available models from multiple backends with rich metadata:
# - Ollama / llama.cpp
# - LM Studio
# - Lemonade
#
# Features:
# - Uses full /api/tags info (parameter_size, quantization, size, family)
# - Smart context window estimation
# - Speed tier based on quantization
# - Model classification (coder, reasoning, fast, vision)

import logging
import time
import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from models.settings import settings
from backend.infrastructure.llm_router import TaskType

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredModel:
    """Rich model representation with computed capabilities."""
    name: str
    backend: str  # "ollama", "llamacpp", "lmstudio", "lemonade"

    # Metadata from backend
    parameter_size: Optional[str] = None
    quantization: Optional[str] = None
    size_bytes: Optional[int] = None
    size_gb: Optional[float] = None
    family: Optional[str] = None
    modified_at: Optional[str] = None

    # Memory state
    is_loaded: bool = False  # Whether model is currently loaded in VRAM
    size_vram_gb: Optional[float] = None  # VRAM used if loaded

    # Computed attributes
    max_context: int = 8192
    speed_tier: str = "medium"  # very_fast, fast, medium, slow
    strengths: List[TaskType] = field(default_factory=list)

    is_coder: bool = False
    is_reasoning: bool = False
    is_vision: bool = False

    def __post_init__(self):
        if self.size_bytes and not self.size_gb:
            self.size_gb = round(self.size_bytes / (1024 ** 3), 2)


class ModelDiscovery:
    """Discovers and enriches models from multiple local LLM backends."""

    def __init__(self, timeout: float = 4.0):
        self.timeout = timeout
        self._cache: List[DiscoveredModel] = []
        self._cache_lock = Lock()
        self._endpoints: Optional[Dict[str, Dict]] = None

    def _get_endpoints(self) -> Dict[str, Dict]:
        """Load endpoints from settings (cached)."""
        if self._endpoints is not None:
            return self._endpoints

        try:
            self._endpoints = {
                "ollama": {
                    "url": f"{settings.ollama_url}/api/tags",
                    "model_path": "models",
                    "backend_name": "ollama"
                },
                "llamacpp": {
                    "url": f"{settings.llamacpp_url}/api/tags",
                    "model_path": "models",
                    "backend_name": "llamacpp"
                },
                "lmstudio": {
                    "url": f"{settings.lmstudio_url}/api/v1/models",
                    "model_path": "data",
                    "backend_name": "lmstudio"
                },
                "lemonade": {
                    "url": f"{settings.lemonade_url}/api/v1/models",
                    "model_path": "models",
                    "backend_name": "lemonade"
                },
            }
        except Exception as e:
            logger.warning(f"Failed to load settings for discovery: {e}")
            self._endpoints = {
                "ollama": {"url": "http://localhost:11434/api/tags", "model_path": "models", "backend_name": "ollama"},
                "llamacpp": {"url": "http://localhost:8080/api/tags", "model_path": "models", "backend_name": "llamacpp"},
                "lmstudio": {"url": "http://localhost:1234/api/v1/models", "model_path": "data", "backend_name": "lmstudio"},
                "lemonade": {"url": "http://localhost:13305/api/v1/models", "model_path": "models", "backend_name": "lemonade"},
            }

        return self._endpoints

    # ==================== Enrichment ====================

    @staticmethod
    def _estimate_max_context(param_size: str, family: str) -> int:
        size = (param_size or "").lower()
        if any(x in size for x in ["70b", "72b", "405b"]):
            return 32768
        if "32b" in size:
            return 16384
        if any(x in size for x in ["13b", "14b", "8b", "9b"]):
            return 8192
        return 4096 if any(x in size for x in ["3b", "4b", "2b", "1b"]) else 8192

    @staticmethod
    def _estimate_speed(quantization: Optional[str], param_size: str) -> str:
        # Handle case where quantization could be a dict or other type
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

    @staticmethod
    def _infer_strengths(name: str) -> List[TaskType]:
        name_lower = name.lower()
        strengths = [TaskType.FAST]

        if any(x in name_lower for x in ["coder", "code", "deepseek", "qwen2.5"]):
            strengths.append(TaskType.CODE)
        if any(x in name_lower for x in ["llama", "mistral", "qwen", "deepseek", "opus"]):
            strengths.append(TaskType.REASONING)
        if any(x in name_lower for x in ["llava", "vision", "moondream", "bakllava"]):
            strengths.append(TaskType.VISION)
            strengths.append(TaskType.ANALYSIS)
        if "gemma" in name_lower:
            strengths.append(TaskType.CREATIVE)

        # Remove duplicates while preserving order
        seen = set()
        return [s for s in strengths if not (s in seen or seen.add(s))]

    def _enrich_model(self, raw: Dict, backend: str) -> DiscoveredModel:
        """Enrich raw model data with smart metadata."""
        name = raw.get("name") or raw.get("id") or raw.get("key", "")

        details = raw.get("details", {}) or {}
        param_size = details.get("parameter_size")
        quant = details.get("quantization_level")
        family = details.get("family")

        size_bytes = raw.get("size") or raw.get("size_bytes")

        model = DiscoveredModel(
            name=name,
            backend=backend,
            parameter_size=param_size,
            quantization=quant,
            size_bytes=size_bytes,
            family=family,
            modified_at=raw.get("modified_at"),
        )

        # Compute capabilities
        model.max_context = self._estimate_max_context(param_size or "", family or "")
        model.speed_tier = self._estimate_speed(quant or "", param_size or "")
        model.strengths = self._infer_strengths(name)

        model.is_coder = TaskType.CODE in model.strengths
        model.is_reasoning = TaskType.REASONING in model.strengths
        model.is_vision = TaskType.VISION in model.strengths

        return model

    # ==================== Discovery Methods ====================

    def _discover_backend(self, backend: str) -> List[DiscoveredModel]:
        """Generic backend discovery - handles both /api/tags and /api/v1/models."""
        config = self._get_endpoints()[backend]
        models: List[DiscoveredModel] = []

        try:
            resp = requests.get(config["url"], timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            # /api/tags returns {"models": [...]}
            # /api/v1/models returns {"data": [...]} or {"models": [...]}
            items = data.get("models") or data.get("data") or []

            for item in items:
                # /api/tags: has "name" directly
                # /api/v1: has "id" - needs wrapping
                raw = item if "name" in item else {
                    "name": item.get("id", ""),
                    "size": item.get("size", 0),
                    "details": {
                        "parameter_size": item.get("parameters"),
                        "quantization_level": item.get("quantization"),
                    }
                }
                models.append(self._enrich_model(raw, backend))

            logger.info(f"[ModelDiscovery] {backend}: {len(models)} models found")
        except requests.RequestException as e:
            logger.debug(f"[ModelDiscovery] {backend} not available: {e}")
        except Exception as e:
            logger.warning(f"[ModelDiscovery] Error discovering {backend}: {e}")

        return models

    def _discover_ollama(self) -> List[DiscoveredModel]:
        return self._discover_backend("ollama")

    def _discover_llamacpp(self) -> List[DiscoveredModel]:
        return self._discover_backend("llamacpp")

    def _discover_lmstudio(self) -> List[DiscoveredModel]:
        return self._discover_backend("lmstudio")

    def _discover_lemonade(self) -> List[DiscoveredModel]:
        return self._discover_backend("lemonade")

    def _get_loaded_models_ollama(self) -> Dict[str, Dict]:
        """Get models currently loaded in Ollama's memory."""
        try:
            endpoint = self._get_endpoints()["ollama"]["url"].replace("/api/tags", "/api/ps")
            resp = requests.get(endpoint, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            # Build a map of model names to their loaded status
            loaded_map = {}
            for model_data in data.get("models", []):
                model_name = model_data.get("name", "")
                size_vram = model_data.get("size_vram", 0)
                size_vram_gb = round(size_vram / (1024 ** 3), 2) if size_vram else None

                loaded_map[model_name] = {
                    "is_loaded": True,
                    "size_vram_gb": size_vram_gb
                }

            logger.debug(f"[ModelDiscovery] Ollama has {len(loaded_map)} models loaded in memory")
            return loaded_map
        except Exception as e:
            logger.debug(f"[ModelDiscovery] Could not get Ollama loaded models: {e}")
            return {}

    def discover_all(self, force_refresh: bool = False) -> List[DiscoveredModel]:
        """Discover models from all backends in parallel."""
        with self._cache_lock:
            if self._cache and not force_refresh:
                return self._cache.copy()

        all_models: List[DiscoveredModel] = []

        # Get loaded models from Ollama
        loaded_ollama = self._get_loaded_models_ollama()

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._discover_ollama): "ollama",
                executor.submit(self._discover_llamacpp): "llamacpp",
                executor.submit(self._discover_lmstudio): "lmstudio",
                executor.submit(self._discover_lemonade): "lemonade",
            }

            for future in as_completed(futures):
                try:
                    models = future.result()
                    # Mark loaded models
                    for model in models:
                        if model.backend == "ollama" and model.name in loaded_ollama:
                            model.is_loaded = True
                            model.size_vram_gb = loaded_ollama[model.name]["size_vram_gb"]
                    all_models.extend(models)
                except Exception as e:
                    logger.debug(f"Discovery failed for {futures[future]}: {e}")

        with self._cache_lock:
            self._cache = all_models

        return all_models

    def refresh(self) -> List[DiscoveredModel]:
        """Force refresh the cache."""
        return self.discover_all(force_refresh=True)

    # ==================== Convenience Methods ====================

    def get_model_names(self) -> List[str]:
        return [m.name for m in self.discover_all()]

    def get_models_by_backend(self, backend: str) -> List[DiscoveredModel]:
        return [m for m in self.discover_all() if m.backend == backend]

    def get_models_summary(self) -> List[Dict]:
        return [
            {
                "name": m.name,
                "backend": m.backend,
                "size_gb": m.size_gb,
                "parameter_size": m.parameter_size,
                "quantization": m.quantization,
                "speed_tier": m.speed_tier,
                "max_context": m.max_context,
                "strengths": [s.value for s in m.strengths],
            }
            for m in self.discover_all()
        ]

    def is_model_available(self, model_name: str) -> bool:
        return any(m.name == model_name for m in self.discover_all())
    
    def get_models_for_preset(self, preset_id: str) -> Dict[str, Optional[DiscoveredModel]]:
        """
        Get best available models for a preset.
        
        Args:
            preset_id: "light", "balanced", or "heavy"
            
        Returns:
            Dict with "fast", "reasoning", "code" keys and DiscoveredModel or None
        """
        from models.settings import DEFAULT_PRESETS
        
        preset = DEFAULT_PRESETS.get(preset_id)
        if not preset:
            return {"fast": None, "reasoning": None, "code": None}
        
        all_models = self.discover_all()
        
        # Find best match for each model type
        result = {}
        for model_type in ["fast", "reasoning", "code"]:
            target_model = getattr(preset, f"model_{model_type}", "")
            
            # Exact match
            exact = next((m for m in all_models if m.name == target_model), None)
            if exact:
                result[model_type] = exact
                continue
            
            # Partial match (e.g., "qwen3.5" matches "qwen3.5:9b")
            partial = next((m for m in all_models if target_model in m.name or m.name in target_model), None)
            if partial:
                result[model_type] = partial
                continue
            
            # Fallback: find any model of appropriate size for preset
            if preset_id == "light":
                # Prefer small models
                result[model_type] = next((m for m in all_models if m.speed_tier == "very_fast"), all_models[0] if all_models else None)
            elif preset_id == "balanced":
                # Prefer medium models
                result[model_type] = next((m for m in all_models if m.speed_tier == "fast"), all_models[0] if all_models else None)
            else:  # heavy
                # Prefer larger models
                result[model_type] = next((m for m in all_models if m.speed_tier == "slow"), all_models[0] if all_models else None)
        
        return result
    
    def get_preset_recommendations(self) -> Dict[str, Dict[str, Any]]:
        """
        Get preset recommendations with available models.
        
        Returns:
            Dict with preset_id -> {preset_info, available_models, is_fully_available}
        """
        from models.settings import DEFAULT_PRESETS
        
        recommendations = {}
        
        for preset_id, preset in DEFAULT_PRESETS.items():
            models = self.get_models_for_preset(preset_id)
            
            # Check if all required models are available
            is_available = all(models.values())
            
            # Count available models
            available_count = sum(1 for m in models.values() if m is not None)
            
            recommendations[preset_id] = {
                "preset": preset,
                "models": {
                    "fast": models["fast"].name if models["fast"] else None,
                    "reasoning": models["reasoning"].name if models["reasoning"] else None,
                    "code": models["code"].name if models["code"] else None,
                },
                "is_available": is_available,
                "available_count": available_count,
                "total_required": 3,
            }
        
        return recommendations
    
    def auto_select_best_preset(self) -> str:
        """
        Automatically select the best preset based on available models.
        
        Returns:
            Preset ID that has the most models available
        """
        recommendations = self.get_preset_recommendations()
        
        # Sort by availability (most models first)
        sorted_presets = sorted(
            recommendations.items(),
            key=lambda x: (x[1]["available_count"], x[1]["is_available"]),
            reverse=True
        )
        
        # Return best available preset
        return sorted_presets[0][0] if sorted_presets else "balanced"


# ====================== Singleton ======================

_discovery: Optional[ModelDiscovery] = None


def get_model_discovery() -> ModelDiscovery:
    global _discovery
    if _discovery is None:
        _discovery = ModelDiscovery()
    return _discovery


# Convenience exports
def discover_available_models(force_refresh: bool = False) -> List[DiscoveredModel]:
    return get_model_discovery().discover_all(force_refresh)


def is_model_available(model_name: str) -> bool:
    return get_model_discovery().is_model_available(model_name)


def get_models_for_preset(preset_id: str) -> Dict[str, Optional[DiscoveredModel]]:
    """Get best available models for a preset."""
    return get_model_discovery().get_models_for_preset(preset_id)


def get_preset_recommendations() -> Dict[str, Dict[str, Any]]:
    """Get preset recommendations with available models."""
    return get_model_discovery().get_preset_recommendations()


def auto_select_best_preset() -> str:
    """Automatically select the best preset based on available models."""
    return get_model_discovery().auto_select_best_preset()


__all__ = [
    "ModelDiscovery",
    "DiscoveredModel",
    "TaskType",
    "get_model_discovery",
    "discover_available_models",
    "is_model_available",
    "ModelDiscovery",
    "DiscoveredModel",
    "TaskType",
    "get_model_discovery",
    "discover_available_models",
    "is_model_available",
    "get_models_for_preset",
    "get_preset_recommendations",
    "auto_select_best_preset",
]