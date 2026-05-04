# services/model_discovery.py - Dynamic Model Discovery
#
# Discovers available models from multiple backends with rich metadata:
# - Ollama / llama.cpp (uses same API)
# - LM Studio
# - Lemonade
#
# Features:
# - Uses full /api/tags info (parameter_size, quantization, size, family)
# - Smart context window estimation
# - Speed tier based on quantization
# - Model classification (coder, reasoning, fast, vision)

import logging
import re
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task type classification for model capabilities"""
    CODE = "code"
    REASONING = "reasoning"
    FAST = "fast"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    VISION = "vision"


@dataclass
class DiscoveredModel:
    """A model discovered from a backend with rich metadata"""
    name: str
    backend: str  # "ollama", "lmstudio", "lemonade"
    # Rich metadata from API
    parameter_size: Optional[str] = None  # ex: "8.0B", "70B"
    quantization: Optional[str] = None    # ex: "Q4_K_M", "Q5_K_S", "FP16"
    size_bytes: Optional[int] = None
    size_gb: Optional[float] = None
    family: Optional[str] = None
    max_context: int = 8192  # Estimated
    # Computed attributes
    speed_tier: str = "fast"  # very_fast, fast, medium, slow
    is_coder: bool = False
    is_reasoning: bool = False
    is_vision: bool = False
    strengths: List[TaskType] = field(default_factory=list)
    # Legacy fields
    size: Optional[str] = None
    modified_at: Optional[str] = None


class ModelDiscovery:
    """
    Dynamic model discovery from multiple backends.
    
    Usage:
        discovery = ModelDiscovery()
        models = discovery.discover_all()  # Returns list of DiscoveredModel
    """
    
    # Backend endpoints - loaded from settings at runtime
    # Note: llama.cpp uses the same API as Ollama (/api/tags), so we detect it as "ollama"
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self._cache: List[DiscoveredModel] = []
        self._cache_lock = Lock()
        
        # Load URLs from settings (lazy import to avoid circular imports)
        self._endpoints: Dict[str, Dict] = {}
        self._load_endpoints()
    
    def _load_endpoints(self):
        """Load backend URLs from settings"""
        try:
            from models.settings import settings
            self._endpoints = {
                "ollama": {
                    "url": f"{settings.ollama_url}/api/tags",
                    "model_path": "models",
                },
                "llamacpp": {
                    "url": f"{settings.llamacpp_url}/api/tags",  # llama.cpp uses Ollama-compatible API
                    "model_path": "models",
                },
                "lmstudio": {
                    "url": f"{settings.lmstudio_url}/api/v1/models",
                    "model_path": "data",
                },
                "lemonade": {
                    "url": f"{settings.lemonade_url}/api/v1/models",
                    "model_path": "models",
                },
            }
        except ImportError as e:
            logger.warning(f"Could not load settings, using defaults: {e}")
            # Fallback to defaults
            self._endpoints = {
                "ollama": {"url": "http://localhost:11434/api/tags", "model_path": "models"},
                "llamacpp": {"url": "http://localhost:8080/api/tags", "model_path": "models"},
                "lmstudio": {"url": "http://localhost:1234/api/v1/models", "model_path": "data"},
                "lemonade": {"url": "http://localhost:13305/api/v1/models", "model_path": "models"},
            }
    
    @property
    def ENDPOINTS(self) -> Dict[str, Dict]:
        """Get endpoints (lazy loaded from settings)"""
        if not self._endpoints:
            self._load_endpoints()
        return self._endpoints
    
    # ==================== Model Enrichment Methods ====================
    
    def _estimate_max_context(self, param_size: str, family: str) -> int:
        """Estimate realistic context window based on parameter size and family"""
        size_str = (param_size or "").lower()
        family_str = (family or "").lower()
        
        if "70b" in size_str or "72b" in size_str:
            return 32768
        elif "32b" in size_str:
            return 16384 if "gemma" not in family_str else 8192
        elif any(x in size_str for x in ["13b", "14b", "8b"]):
            return 8192
        elif any(x in size_str for x in ["3b", "4b", "2b", "1b", "0.8b"]):
            return 4096
        return 8192
    
    def _estimate_speed(self, quantization: str, param_size: str) -> str:
        """Determine speed tier based on quantization and parameter size"""
        quant = (quantization or "").upper()
        size = (param_size or "").lower()
        
        if any(x in quant for x in ["Q2", "Q3", "IQ3"]) or "1b" in size or "0.8b" in size:
            return "very_fast"
        elif "Q4" in quant or "7b" in size or "8b" in size:
            return "fast"
        elif "Q5" in quant or "Q6" in quant:
            return "medium"
        else:
            return "slow"
    
    def _infer_strengths(self, name: str, param_size: str, family: str) -> List[TaskType]:
        """Infer model strengths from name and metadata"""
        name_lower = name.lower()
        strengths = [TaskType.FAST]
        
        # Code detection
        if "coder" in name_lower or "code" in name_lower:
            strengths.append(TaskType.CODE)
        elif "qwen" in name_lower and "2.5" in name_lower:
            strengths.append(TaskType.CODE)
        
        # Reasoning detection
        if "deepseek" in name_lower or "llama" in name_lower or "mistral" in name_lower:
            strengths.append(TaskType.REASONING)
        elif "qwen" in name_lower and "opus" in name_lower:
            strengths.append(TaskType.REASONING)
        
        # Vision detection
        if any(x in name_lower for x in ["vision", "llava", "moondream", "vision"]):
            strengths.append(TaskType.VISION)
            strengths.append(TaskType.ANALYSIS)
        
        # Creative (Gemma)
        if "gemma" in name_lower:
            strengths.append(TaskType.CREATIVE)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(strengths))
    
    def _enrich_model(self, model_data: Dict, backend: str) -> DiscoveredModel:
        """Enrich model data with computed attributes"""
        name = model_data.get("name", "")
        details = model_data.get("details", {})
        
        # Extract metadata
        param_size = details.get("parameter_size")
        quant = details.get("quantization_level")
        family = details.get("family")
        size_bytes = model_data.get("size", 0)
        
        # Compute derived attributes
        size_gb = round(size_bytes / (1024**3), 2) if size_bytes else None
        max_context = self._estimate_max_context(param_size or "", family or "")
        speed_tier = self._estimate_speed(quant or "", param_size or "")
        strengths = self._infer_strengths(name, param_size or "", family or "")
        
        # Detect specific capabilities
        name_lower = name.lower()
        is_coder = "coder" in name_lower or ("qwen" in name_lower and "2.5" in name_lower)
        is_reasoning = "deepseek" in name_lower or "llama" in name_lower or "mistral" in name_lower
        is_vision = any(x in name_lower for x in ["vision", "llava", "moondream"])
        
        return DiscoveredModel(
            name=name,
            backend=backend,
            parameter_size=param_size,
            quantization=quant,
            size_bytes=size_bytes,
            size_gb=size_gb,
            family=family,
            max_context=max_context,
            speed_tier=speed_tier,
            is_coder=is_coder,
            is_reasoning=is_reasoning,
            is_vision=is_vision,
            strengths=strengths,
            size=str(size_bytes) if size_bytes else None,
            modified_at=model_data.get("modified_at"),
        )
    
    # ==================== Discovery Methods ====================
    
    def _discover_ollama(self) -> List[DiscoveredModel]:
        """Discover models from Ollama with rich metadata"""
        models = []
        try:
            response = requests.get(
                self.ENDPOINTS["ollama"]["url"],
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            for model in data.get("models", []):
                enriched = self._enrich_model(model, "ollama")
                models.append(enriched)
            logger.info(f"[ModelDiscovery] Ollama: found {len(models)} models")
        except requests.RequestException as e:
            logger.debug(f"[ModelDiscovery] Ollama unavailable: {e}")
        return models
    
    def _discover_llamacpp(self) -> List[DiscoveredModel]:
        """Discover models from llama.cpp (uses Ollama-compatible API)"""
        models = []
        try:
            response = requests.get(
                self.ENDPOINTS["llamacpp"]["url"],
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            # llama.cpp returns same format as Ollama
            for model in data.get("models", []):
                enriched = self._enrich_model(model, "ollama")  # Treat as Ollama
                models.append(enriched)
            logger.info(f"[ModelDiscovery] llama.cpp: found {len(models)} models")
        except requests.RequestException as e:
            logger.debug(f"[ModelDiscovery] llama.cpp unavailable: {e}")
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
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._discover_ollama): "ollama",
                executor.submit(self._discover_llamacpp): "llamacpp",
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
    
    def get_models_summary(self) -> List[Dict]:
        """Get summary of all discovered models (useful for UI/debug)"""
        models = self.discover_all()
        return [
            {
                "name": m.name,
                "backend": m.backend,
                "size_gb": m.size_gb,
                "parameter_size": m.parameter_size,
                "quantization": m.quantization,
                "speed_tier": m.speed_tier,
                "max_context": m.max_context,
                "is_coder": m.is_coder,
                "is_reasoning": m.is_reasoning,
                "is_vision": m.is_vision,
                "strengths": [s.value for s in m.strengths],
            }
            for m in models
        ]
    
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