# services/model_discovery.py - Dynamic Model Discovery
#
# Discovers available models from multiple backends:
# - Ollama (localhost:11434)
# - LM Studio (localhost:1234)
# - Lemonade (localhost:13305)

import logging
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredModel:
    """A model discovered from a backend"""
    name: str
    backend: str  # "ollama", "lmstudio", "lemonade"
    size: Optional[str] = None
    modified_at: Optional[str] = None


class ModelDiscovery:
    """
    Dynamic model discovery from multiple backends.
    
    Usage:
        discovery = ModelDiscovery()
        models = discovery.discover_all()  # Returns list of DiscoveredModel
    """
    
    # Backend endpoints for model listing
    ENDPOINTS = {
        "ollama": {
            "url": "http://localhost:11434/api/tags",
            "model_path": "models",
        },
        "lmstudio": {
            "url": "http://localhost:1234/api/v1/models",
            "model_path": "data",
        },
        "lemonade": {
            "url": "http://localhost:13305/api/v1/models",
            "model_path": "models",
        },
    }
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self._cache: List[DiscoveredModel] = []
        self._cache_lock = Lock()
        self._cache_time: Optional[float] = None
    
    def _discover_ollama(self) -> List[DiscoveredModel]:
        """Discover models from Ollama"""
        models = []
        try:
            response = requests.get(
                self.ENDPOINTS["ollama"]["url"],
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            for model in data.get("models", []):
                models.append(DiscoveredModel(
                    name=model.get("name", ""),
                    backend="ollama",
                    size=model.get("size"),
                    modified_at=model.get("modified_at"),
                ))
            logger.info(f"[ModelDiscovery] Ollama: found {len(models)} models")
        except requests.RequestException as e:
            logger.debug(f"[ModelDiscovery] Ollama unavailable: {e}")
        return models
    
    def _discover_lmstudio(self) -> List[DiscoveredModel]:
        """Discover models from LM Studio"""
        models = []
        try:
            response = requests.get(
                self.ENDPOINTS["lmstudio"]["url"],
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            # LM Studio returns { models: [...] }
            for model in data.get("models", []):
                models.append(DiscoveredModel(
                    name=model.get("display_name") or model.get("key", ""),
                    backend="lmstudio",
                    size=model.get("size_bytes"),
                ))
            logger.info(f"[ModelDiscovery] LM Studio: found {len(models)} models")
        except requests.RequestException as e:
            logger.debug(f"[ModelDiscovery] LM Studio unavailable: {e}")
        return models
    
    def _discover_lemonade(self) -> List[DiscoveredModel]:
        """Discover models from Lemonade"""
        models = []
        try:
            response = requests.get(
                self.ENDPOINTS["lemonade"]["url"],
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            for model in data.get("models", []):
                models.append(DiscoveredModel(
                    name=model.get("name", ""),
                    backend="lemonade",
                    size=model.get("size"),
                ))
            logger.info(f"[ModelDiscovery] Lemonade: found {len(models)} models")
        except requests.RequestException as e:
            logger.debug(f"[ModelDiscovery] Lemonade unavailable: {e}")
        return models
    
    def discover_all(self) -> List[DiscoveredModel]:
        """
        Discover models from all backends in parallel.
        
        Returns:
            List of DiscoveredModel from all available backends
        """
        all_models = []
        
        # Run all discovery methods in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._discover_ollama): "ollama",
                executor.submit(self._discover_lmstudio): "lmstudio",
                executor.submit(self._discover_lemonade): "lemonade",
            }
            
            for future in as_completed(futures):
                backend = futures[future]
                try:
                    models = future.result()
                    all_models.extend(models)
                except Exception as e:
                    logger.debug(f"[ModelDiscovery] {backend} failed: {e}")
        
        # Update cache
        with self._cache_lock:
            self._cache = all_models
        
        return all_models
    
    def get_model_names(self) -> List[str]:
        """Get just the model names (without backend prefix)"""
        models = self.discover_all()
        return [m.name for m in models]
    
    def get_models_by_backend(self, backend: str) -> List[DiscoveredModel]:
        """Get models from a specific backend"""
        models = self.discover_all()
        return [m for m in models if m.backend == backend]
    
    def is_model_available(self, model_name: str) -> bool:
        """Check if a model is available on any backend"""
        models = self.discover_all()
        return any(m.name == model_name for m in models)


# Singleton instance
_discovery: Optional[ModelDiscovery] = None


def get_model_discovery() -> ModelDiscovery:
    """Get singleton model discovery instance"""
    global _discovery
    if _discovery is None:
        _discovery = ModelDiscovery()
    return _discovery


def discover_available_models() -> List[DiscoveredModel]:
    """Convenience function to discover all available models"""
    return get_model_discovery().discover_all()


def is_model_available(model_name: str) -> bool:
    """Convenience function to check if model is available"""
    return get_model_discovery().is_model_available(model_name)


__all__ = [
    "ModelDiscovery",
    "DiscoveredModel",
    "get_model_discovery",
    "discover_available_models",
    "is_model_available",
]