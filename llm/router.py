# llm/router.py - Intelligent Multi-Model Router
"""
Role: Intelligent routing of tasks to best model based on keywords
Used by: orchestrator, code_review, streaming service
"""

from dataclasses import dataclass
from typing import Literal, Optional, Iterator
import logging

from models.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """LLM Backend Configuration"""
    url: str = ""
    model: str = ""
    timeout: int = 120
    backend: str = "ollama"


class OllamaClient:
    """Unified client supporting multiple backends (Ollama, LM Studio, etc.)"""

    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Synchronous generation."""
        import json
        import requests

        model = model or self.config.model
        url = self.config.url or f"{settings.ollama_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {"temperature": temperature}
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.config.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get('response', '')
        except requests.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            error_msg = str(e).lower()
            if "subscription" in error_msg or "upgrade" in error_msg:
                return "[Error: Ce modèle nécessite un abonnement. Utilisez un modèle local.]"
            elif "404" in error_msg:
                return "[Error: Modèle non trouvé. Vérifiez 'ollama list']"
            elif "connection" in error_msg:
                return "[Error: Impossible de se connecter à Ollama.]"
            return f"[OllamaError: {e}]"

    def stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Streaming response."""
        import json
        import requests

        model = model or self.config.model
        backend = self.config.backend or "ollama"

        # Determine URL and payload format based on backend
        if backend in ("lmstudio", "lemonade"):
            url = self.config.url or f"{settings.ollama_url}/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "temperature": temperature
            }
        else:
            # Ollama format
            url = self.config.url or f"{settings.ollama_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "system": system_prompt or "",
                "stream": True,
                "options": {"temperature": temperature}
            }

        try:
            with requests.post(url, json=payload, stream=True, timeout=self.config.timeout) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        text = line.decode().strip()
                        if not text:
                            continue
                        # Handle SSE format
                        if text.startswith("data: "):
                            text = text[6:]
                        if text == "[DONE]":
                            break
                        try:
                            data = json.loads(text)
                            # Parse based on backend format
                            if backend in ("lmstudio", "lemonade", "llamacpp"):
                                content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            else:
                                # Ollama format
                                content = data.get('response', '') or data.get('thinking', '')
                            if content:
                                yield content
                            if data.get("done", False):
                                break
                            choices = data.get("choices", [])
                            if choices and choices[0].get("finish_reason"):
                                break
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse stream line: {text[:50]}")
        except requests.RequestException as e:
            logger.error(f"[OllamaClient.stream] Request error: {e}")
            error_msg = str(e)
            if "subscription" in error_msg.lower() or "upgrade" in error_msg.lower():
                yield "[Error: Ce modèle nécessite un abonnement Ollama. Veuillez sélectionner un modèle local (qwen3.6, gemma4, lfm2, nemotron-cascade-2, qwen3.5:9b)]"
            elif "404" in error_msg:
                yield "[Error: Modèle non trouvé. Vérifiez que le modèle est bien installé localement avec 'ollama list']"
            elif "connection" in error_msg.lower():
                yield "[Error: Impossible de se connecter à Ollama. Vérifiez que le service est démarré.]"
            else:
                yield f"[Error: {e}]"


# ==================== CONFIG ====================

@dataclass
class ModelsConfig:
    """Configuration multi-modèles"""
    fast: str = ""
    reasoning: str = ""
    code: str = ""
    reasoner: str = ""
    ollama_url: str = ""
    timeout: int = 120

    @classmethod
    def from_settings(cls) -> "ModelsConfig":
        from models.settings import settings
        return cls(
            fast=settings.model_fast,
            reasoning=settings.model_reasoning,
            code=settings.model_code,
            reasoner=settings.model_reasoning,
            ollama_url=f"{settings.ollama_url}/api/generate",
            timeout=120,
        )


# Singleton settings
_settings = ModelsConfig.from_settings()


# ==================== ROUTER ====================

class LLMRouter:
    """Intelligent model router with weighted scoring."""

    def __init__(self, config: Optional[ModelsConfig] = None):
        self.config = config or _settings

    def get_model_for_task(self, task: str) -> str:
        """Score-based model selection."""
        task_lower = task.lower().strip()

        scores = {"code": 0, "reasoner": 0, "fast": 0}

        # Weighted keywords
        keywords = {
            "code": {"code": 2, "implement": 2, "function": 1, "def ": 2, "class ": 2, 
                     "bug": 2, "fix": 2, "refactor": 2},
            "reasoner": {"debug": 3, "architecture": 3, "plan": 2, "analyze": 2, 
                        "design": 2, "strategy": 2, "complex": 2, "optimize": 2},
            "fast": {"explain": 2, "describe": 2, "what": 1, "who": 1, "simple": 2, 
                    "summarize": 2}
        }

        for category, kw_dict in keywords.items():
            for kw, weight in kw_dict.items():
                if kw in task_lower:
                    scores[category] += weight

        # Select highest scoring category
        if scores["code"] >= max(scores["reasoner"], scores["fast"]):
            return self.config.code
        elif scores["reasoner"] >= scores["fast"]:
            return self.config.reasoner
        else:
            return self.config.fast

    def _create_model_config(self, model_name: str) -> ModelConfig:
        return ModelConfig(
            url=self.config.ollama_url,
            model=model_name,
            timeout=self.config.timeout,
        )

    def get_for_task(self, task: str) -> OllamaClient:
        model_name = self.get_model_for_task(task)
        logger.debug(f"Routing task → {model_name}")
        return OllamaClient(self._create_model_config(model_name))

    def get_for_mode(self, mode: str) -> OllamaClient:
        """Get client by explicit mode."""
        mode_map = {
            "fast": self.config.fast,
            "code": self.config.code,
            "reasoning": self.config.reasoning,
            "reasoner": self.config.reasoner,
        }
        model_name = mode_map.get(mode.lower(), self.config.fast)
        return OllamaClient(self._create_model_config(model_name))

    def generate(self, prompt: str, mode: str = "fast") -> str:
        """Convenience method."""
        client = self.get_for_mode(mode)
        return client.generate(prompt)


# ====================== Singleton ======================

_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


__all__ = ["LLMRouter", "OllamaClient", "ModelConfig", "get_llm_router"]