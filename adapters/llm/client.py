# adapters/llm/client.py - LLM Client Adapter
#
# Ollama client adapter for LLM generation.

import logging
from typing import Optional, Iterator
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for LLM backend"""
    url: str = "http://localhost:11434/api/generate"
    model: str = "gemma4:latest"
    timeout: int = 60


class OllamaClient:
    """
    Client for Ollama local LLM.
    
    Features:
    - Fast local inference
    - Streaming support
    - Configurable timeouts
    """
    
    def __init__(self, config: ModelConfig = None):
        self.url = getattr(config, 'url', 'http://localhost:11434/api/generate') if config else "http://localhost:11434/api/generate"
        self.model = getattr(config, 'model', 'gemma4:latest') if config else "gemma4:latest"
        self.timeout = getattr(config, 'timeout', 60) if config else 60
    
    def generate(
        self, 
        prompt: str, 
        model: str = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Generate response from LLM"""
        model = model or self.model
        
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {"temperature": temperature}
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json().get('response', '')
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
        """Stream response from LLM"""
        model = model or self.model
        
        payload = {
            "model": model,
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
                        yield line.decode()
        except requests.RequestException as e:
            yield f"[Error: {e}]"


__all__ = ["OllamaClient", "ModelConfig"]