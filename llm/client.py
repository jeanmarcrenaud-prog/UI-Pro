# llm/client.py - LLM Client Interfaces & Factory
#
# Role: Protocol-based LLM client interface with Ollama adapter
# Used by: router.py, streaming service, general LLM calls

from dataclasses import dataclass
from typing import Protocol, Iterator, Optional
import logging
import json
import requests

logger = logging.getLogger(__name__)


# ==================== CONFIGURATION ====================

from models.settings import settings as _app_settings


@dataclass
class ModelConfig:
    """Configuration for LLM backend"""
    url: str = ""
    model: str = ""
    timeout: int = 30
    
    def __post_init__(self):
        if not self.url:
            self.url = f"{_app_settings.ollama_url}/api/generate"
        if not self.model:
            self.model = _app_settings.model_fast
        if self.timeout <= 0:
            self.timeout = _app_settings.llm_timeout


# ==================== PROTOCOL ====================

class LLMClient(Protocol):
    """Interface standard pour tous les clients LLM."""
    
    def generate(self, prompt: str, model: str, 
               system_prompt: Optional[str] = None,
               temperature: float = 0.7) -> str: ...
    
    def stream(self, prompt: str, model: str,
              system_prompt: Optional[str] = None,
              temperature: float = 0.7) -> Iterator[str]: ...


# ==================== OLLAMA ADAPTER ====================

class OllamaClient(LLMClient):
    """Ollama local LLM client."""
    
    def __init__(self, config: ModelConfig = None):
        cfg = config or ModelConfig()
        self.url = cfg.url
        self.model = cfg.model
        self.timeout = cfg.timeout
    
    def generate(
        self, 
        prompt: str, 
        model: str = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Generate response from Ollama."""
        model = model or self.model
        
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {"temperature": temperature}
        }
        
        try:
            response = requests.post(
                self.url, 
                json=payload, 
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get('response', '')
        except requests.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            return f"[OllamaError: {e}]"
    
    def stream(
        self, 
        prompt: str, 
        model: str = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Iterator[str]:
        """Stream response from Ollama."""
        model = model or self.model
        
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": True,
            "options": {"temperature": temperature}
        }
        
        try:
            with requests.post(
                self.url, 
                json=payload, 
                stream=True,
                timeout=self.timeout
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        text = line.decode().strip()
                        if not text:
                            continue
                        # Parse JSON line from Ollama
                        try:
                            data = json.loads(text)
                            content = data.get('response', '')
                            if content:
                                yield content
                            if data.get('done', False):
                                break
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse stream line: {text[:50]}")
        except requests.RequestException as e:
            yield f"[Error: {e}]"


# ==================== FACTORY ====================

class LLMFactory:
    """Factory for creating LLM clients."""
    
    def __init__(self):
        self._settings = _app_settings
    
    def create(self, backend: str = "ollama") -> LLMClient:
        """Create LLM client for given backend."""
        if backend == "ollama":
            return OllamaClient(ModelConfig())
        # Fallback to Ollama
        return OllamaClient(ModelConfig())


# ==================== MOCK FOR TESTS ====================

class MockLLMClient(LLMClient):
    """Mock LLM for testing."""
    
    def __init__(
        self, 
        responses: list[str] = None,
        config: ModelConfig = None
    ):
        self.responses = responses or [
            "Mock response 1",
            "Mock response 2",
            "Mock response 3",
        ]
        self._index = 0
        self._config = config or ModelConfig()
    
    def generate(
        self, 
        prompt: str, 
        model: str = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Return next mock response."""
        response = self.responses[self._index]
        self._index = (self._index + 1) % len(self.responses)
        return response
    
    def stream(
        self, 
        prompt: str, 
        model: str = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Iterator[str]:
        """Yield mock responses."""
        for response in self.responses:
            yield response


__all__ = [
    "ModelConfig",
    "LLMClient", 
    "OllamaClient",
    "LLMFactory",
    "MockLLMClient",
]