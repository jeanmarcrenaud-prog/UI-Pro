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
    backend: str = "ollama"  # "ollama" or "lemonade"


class OllamaClient:
    """
    Client for Ollama local LLM.
    
    Features:
    - Fast local inference
    - Streaming support
    - Configurable timeouts
    - Support for Lemonade backend
    """
    
    def __init__(self, config: ModelConfig = None):
        self.url = getattr(config, 'url', 'http://localhost:11434/api/generate') if config else "http://localhost:11434/api/generate"
        self.model = getattr(config, 'model', 'gemma4:latest') if config else "gemma4:latest"
        self.timeout = getattr(config, 'timeout', 60) if config else 60
        self.backend = getattr(config, 'backend', 'ollama') if config else 'ollama'
    
    def _get_url(self) -> str:
        """Get the appropriate URL based on backend"""
        if self.backend == 'lemonade':
            return "http://localhost:13305/api/v1/chat/completions"
        return self.url
    
    def generate(
        self, 
        prompt: str, 
        model: str = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Generate response from LLM"""
        model = model or self.model
        
        if self.backend == 'lemonade':
            return self._generate_lemonade(prompt, model, system_prompt, temperature)
        
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
    
    def _generate_lemonade(self, prompt: str, model: str, system_prompt: Optional[str], temperature: float) -> str:
        """Generate response from Lemonade backend"""
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt or ""},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "stream": False
        }
        
        try:
            response = requests.post(
                "http://localhost:13305/api/v1/chat/completions",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
        except requests.RequestException as e:
            logger.error(f"Lemonade request failed: {e}")
            return f"[LemonadeError: {e}]"
    
    def stream(
        self, 
        prompt: str, 
        model: str = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Iterator[str]:
        """Stream response from LLM"""
        model = model or self.model
        
        if self.backend == 'lemonade':
            return self._stream_lemonade(prompt, model, system_prompt, temperature)
        
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
    
    def _stream_lemonade(self, prompt: str, model: str, system_prompt: Optional[str], temperature: float) -> Iterator[str]:
        """Stream response from Lemonade backend"""
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt or ""},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "stream": True
        }
        
        try:
            with requests.post(
                "http://localhost:13305/api/v1/chat/completions",
                json=payload,
                stream=True,
                timeout=self.timeout
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        data = line.decode()
                        if data.startswith('data: '):
                            import json
                            chunk = json.loads(data[6:])
                            content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if content:
                                yield content
        except requests.RequestException as e:
            yield f"[Error: {e}]"


__all__ = ["OllamaClient", "ModelConfig"]