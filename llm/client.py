# llm/client.py - LLM Client Interfaces & Factory
#
# Role: Protocol-based LLM client interface with Ollama adapter
# Used by: router.py, streaming service, general LLM calls
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

# Load settings once
from models.settings import settings as _app_settings

@dataclass
class ModelConfig:
    """Configuration pour chaque type de backend"""
    url: str = ""
    model: str = ""
    
    def __post_init__(self):
        if not self.url:
            self.url = f"{_app_settings.ollama_url}/api/generate"
        if not self.model:
            self.model = _app_settings.model_fast

@dataclass  
class Settings:
    """Settings globaux (from models.settings)"""
    HF_TOKEN: Optional[str] = None
    OLLAMA_URL: str = ""
    MODEL_FAST: str = ""
    MODEL_REASONING: str = ""  
    OLLAMA_TIMEOUT: int = 60
    HTTP_TIMEOUT: int = 300
    LOG_LEVEL: str = "INFO"
    BACKEND: Literal["ollama", "http"] = "ollama"
    
    def __post_init__(self):
        object.__setattr__(self, 'OLLAMA_URL', _app_settings.ollama_url)
        object.__setattr__(self, 'MODEL_FAST', _app_settings.model_fast)
        object.__setattr__(self, 'MODEL_REASONING', _app_settings.model_reasoning)


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
        from models.settings import settings as _s
        self.url = getattr(config, 'url', f"{_s.ollama_url}/api/generate")
        self.model = getattr(config, 'model', _s.model_fast)
    
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
            from models.settings import settings
            return f"[OllamaError: {e}] {prompt[:10]}..."
    
    def stream(self, prompt: str, model: str,
               system_prompt: Optional[str] = None,
               temperature: float = 0.7) -> Iterator[str]:
        """Streamer réponse Ollama chunk par chunk"""
        import requests
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
                        # Ollama stream: {"response": "...", "done": false}
                        if '"response"' in chunk:
                            yield chunk
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
    
    def __init__(self):
        import settings
        self.settings = settings
    
    def create(self, llm_type: str = None) -> LLMClient:
        """
        Factory pattern pour créer clients appropriés.
        
        Args:
            llm_type: "ollama", "http", ou None pour default
        
        Returns:
            LLMClient adapté au type
        """
        if not llm_type:
            llm_type = self.settings.get("BACKEND", "ollama")
        
        if llm_type == "ollama":
            return OllamaClient(self.settings)
        elif llm_type == "http":
            return OllamaClient(self.settings)  # Fallback
        else:
            return OllamaClient(self.settings)  # Default


# ==================== **5. Mock pour Tests** ====================

@dataclass  
class MockLLMResponse:
    response: str
    tokens: int = 100
    
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
# NOTE: These are examples - uncomment for testing only

if __name__ == "__main__":
    from llm.client import LLMFactory, OllamaClient
    factory = LLMFactory()
    llm = factory.create()
    response = llm.generate("Who is John Doe?", "qwen2.5-coder:32b")
    print(response)

    # Avec system prompt :
    response = llm.generate(
        "Explain quantum physics",
        model="qwen-opus",
        system_prompt="You are a physics expert."
    )

    # Streaming :
    import asyncio
    async def process_streaming():
        async for chunk in llm.stream("Prompt..."):
            print(chunk, end="")

    # Mock pour tests :
    from unittest.mock import patch
    @patch.object(LLMFactory, 'create', create=MockLLMClient)
    def test_with_mock():
        llm = LLMFactory().create()
        assert "mock" in llm.generate("test")
