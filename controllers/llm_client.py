# 🎯 **LLMClient Interface** (Protocol-based DI)
#
# Cette interface abstraite permet :
# - Swap facile (Ollama → HTTP → HF)
# - Mocking pour tests
# - Architecture propre (Inversion de contrôle)
#
# Usage :
#   from llm_factory import get_llm_client
#   llm = get_llm_client(settings)
#
# Tests :
#   with mock_llm():
#       llm = get_llm_client(settings)

from dataclasses import dataclass, field
from typing import Protocol, Iterator, Literal, Optional, Union
import requests
from abc import ABC, abstractmethod


# ==================== **1. CONFIGURATION** ====================

@dataclass
class ModelConfig:
    """Configuration pour chaque type de backend"""
    url: str = "http://localhost:11434/api/generate"
    model: str = "qwen2.5-coder:32b"
    
@dataclass  
class Settings:
    """Settings globaux (de settings.py ou .env)"""
    HF_TOKEN: Optional[str] = None
    OLLAMA_URL: str = "http://localhost:11434"
    MODEL_FAST: str = "qwen2.5-coder:32b"
    MODEL_REASONING: str = "qwen-opus"  
    OLLAMA_TIMEOUT: int = 60
    HTTP_TIMEOUT: int = 300
    LOG_LEVEL: str = "INFO"
    BACKEND: Literal["ollama", "http"] = "ollama"  # Nouveau!


# ==================== **2. INTERFACe** ====================

class LLMClient(Protocol):
    """
    Interface standard pour tous les clients LLM.
    
    Implémentation typique :
      from llm_client import LLMClient
      @dataclass
      class MyLLMClient(LLMClient):
          def generate(self, prompt: str, model: str) -> str:
              return self.api.generate(prompt, model)
    """
    def generate(self, prompt: str, model: str, 
                 system_prompt: Optional[str] = None,
                 temperature: float = 0.7) -> str: ...
    
    def stream(self, prompt: str, model: str,
               system_prompt: Optional[str] = None,
               temperature: float = 0.7) -> Iterator[str]: ...


# ==================== **3. ADAPTateur Ollama** ====================

class OllamaClient(LLMClient):
    """
    Adaptateur pour Ollama local.
    
    Avantages :
      ✅ Rapide (latence <50ms)
      ✅ Local (pas de cloud)  
      ✅ Gratuit (open source)
    
    Configuration :
      OLLAMA_URL=http://localhost:11434
      MODEL=qwen2.5-coder:32b
    """
    
    def __init__(self, config: Settings | ModelConfig = None):
        self.url = getattr(config, 'url', 'http://localhost:11434/api/generate')
        self.model = getattr(config, 'model', 'qwen2.5-coder:32b')
    
    def generate(self, prompt: str, model: str,
                 system_prompt: Optional[str] = None,
                 temperature: float = 0.7) -> str:
        """Generer réponse Ollama complète"""
        import requests
        
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model or self.model,
            "prompt": prompt, 
            "system": system_prompt or "",
            "stream": False,
            "options": {"temperature": temperature}
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=60)
            response.raise_for_status()
            return response.json().get('response', '')
        except requests.RequestException as e:
            from settings import settings
            return f"[OllamaError: {e}] {prompt[:10]}..."
    
    def stream(self, prompt: str, model: str,
               system_prompt: Optional[str] = None,
               temperature: float = 0.7) -> Iterator[str]:
        """Streamer réponse Ollama chunk par chunk"""
        import requests
        import json
        import time
        
headers = {"Content-Type": "application/json"}
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": True,
            "options": {"temperature": temperature}
        }
        
        try:
            with requests.post(self.url, json=payload, stream=True) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        chunk = line.decode().strip()
                        # Parse JSON from Ollama stream - extract only "response" field
                        try:
                            data = json.loads(chunk)
                            # Ollama stream returns {"response": "...", "done": false, ...}
                            response_text = data.get("response", "")
                            # Only yield actual response text, not full JSON
                            if response_text:
                                yield response_text
                            if data.get("done", False):
                                # End of stream
                                break
                        except json.JSONDecodeError:
                            # If JSON parsing fails, skip or yield raw chunk
                            # This handles malformed JSON chunks
                            pass
        except requests.RequestException as e:
            yield f"[Error: {e}]"


# ==================== **4. Factory Singleton** ====================

class LLMFactory:
    """
    Singleton factory pour créer LLMs dynamiquement.
    
    Usage :
      from llm_factory import LLMFactory
      factory = LLMFactory()
      llm = factory.create("OLLAMA_URL=http://...")
    """
    
    def __init__(self, settings_instance: Settings = None):
        """
        Initialize factory with settings instance.
        
        Args:
            settings_instance: Settings instance (from models.settings or loaded from .env)
        """
        self.settings = settings_instance
        
        # If no settings instance provided, load default
        if self.settings is None:
            from models.settings import settings
            self.settings = settings
    
    def create(self, llm_type: str = None) -> LLMClient:
        """
        Factory pattern pour créer clients appropriés.
        
        Args:
            llm_type: "ollama", "http", ou None pour default
        
        Returns:
            LLMClient adapté au type
        
        Example:
            llm = factory.create("OLLAMA_URL=http://...")
        """
        if not llm_type:
            llm_type = getattr(self.settings, 'BACKEND', "ollama")
        
        # Get model from settings
        model = getattr(self.settings, 'MODEL_FAST', "qwen2.5-coder:32b")
        
        if llm_type == "ollama":
            return OllamaClient(self.settings, model=model)
        elif llm_type == "http":
            return OllamaClient(self.settings, model=model)  # Fallback for HTTP mode
        else:
            return OllamaClient(self.settings, model=model)  # Default to Ollama


# ==================== **5. Mock pour Tests** ====================

@dataclass  
class MockLLMResponse:
    response: str
    tokens: int = 100

    class MockLLMClient(_LLMClient):
        """
        Mock LLM pour tests.
        
        Usage :
          from llm_client import MockLLMClient
          with MockLLMClient() as mock:
              llm = factory.create()
        """
        
        def __init__(self, responses: list[str] = None):
            self.responses = responses or [
                "Ceci est une réponse mock",
                "Ceci est la deuxième réponse",  
                "Fin de la réponse mock"
            ]
            self.call_count = 0
        
        def generate(self, prompt: str, model: str,
                     **kwargs) -> str:
            self.call_count += 1
            return self.responses[self.call_count % len(self.responses)]
        
        def stream(self, prompt: str, model: str, **kwargs) -> Iterator[str]:
            yield self.generate(prompt, model)
        
        @classmethod
        def make(cls, responses: list[str] = None) -> "MockLLMClient":
            """Factory method to create instance"""
            return cls(responses)
    
class MockLLMClient(LLMClient):
    """
    Mock LLM pour tests.
    
    Usage :
      from llm_client import MockLLMClient
      with MockLLMClient() as mock:
          llm = factory.create()
    """
    
    def __init__(self, responses: list[str] = None):
        self.responses = responses or [
            "Ceci est une réponse mock",
            "Ceci est la deuxième réponse",  
            "Fin de la réponse mock"
        ]
        self.call_count = 0
    
    def generate(self, prompt: str, model: str,
                 **kwargs) -> str:
        self.call_count += 1
        return self.responses[self.call_count % len(self.responses)]
    
    def stream(self, prompt: str, model: str, **kwargs) -> Iterator[str]:
        yield self.generate(prompt, model)


# ==================== **6. Exemples d'Usage** ====================

# Usage basique :
# (_examples demonstrate usage - comment out to avoid execution on import)
