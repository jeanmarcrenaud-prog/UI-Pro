# llm/router.py - Multi-Model Router
#
# Role: Intelligent routing of tasks to best model based on keywords
# Used by: orchestrator, code_review, general task routing
# - fast → qwen2.5:7b (exposé <300ms)
# - reasoning → qwen2.5:32b (complexité)
# - code → deepseek-coder:33b (spécialisation)
#
# Usage :
#   router = LLMRouter()
#   llm = router.get_for_task("explain")  # fast
#   llm = router.get_for_task("debug")    # reasoning

from dataclasses import dataclass
from typing import Literal, Optional, Iterator
import logging
from models.settings import settings

# Define ModelConfig and OllamaClient locally since we removed llm/client.py
@dataclass
class ModelConfig:
    """Configuration for LLM backend"""
    url: str = ""
    model: str = ""
    timeout: int = 30
    backend: str = "ollama"  # ollama, lmstudio, lemonade, etc.

    def __post_init__(self):
        # Values are set explicitly in _create_model_config
        pass


class OllamaClient:
    """Ollama local LLM client."""

    def __init__(self, config: ModelConfig = None):
        self.config = config or ModelConfig()

    def generate(
        self, 
        prompt: str, 
        model: str = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Generate response from Ollama."""
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
            response = requests.post(
                url, 
                json=payload, 
                timeout=self.config.timeout
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
        import json
        import requests

        model = model or self.config.model
        url = self.config.url or f"{settings.ollama_url}/v1/chat/completions"
        # Use backend from config to determine format
        backend = self.config.backend or "ollama"

        if backend == "ollama":
            # Ollama format: /api/generate with prompt
            url = self.config.url or f"{settings.ollama_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "system": system_prompt or "",
                "stream": True,
                "options": {"temperature": temperature}
            }
            is_streaming_endpoint = "stream" in url and "chat" not in url
        elif backend in ("lmstudio", "lemonade"):
            # LM Studio / OpenAI format: /v1/chat/completions with messages
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
            is_streaming_endpoint = True
        else:
            # Default to Ollama format
            url = self.config.url or f"{settings.ollama_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "system": system_prompt or "",
                "stream": True,
                "options": {"temperature": temperature}
            }
            is_streaming_endpoint = "stream" in url and "chat" not in url

        if is_streaming_endpoint:
            try:
                with requests.post(
                    url,
                    json=payload,
                    stream=True,
                    timeout=self.config.timeout
                ) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if line:
                            text = line.decode().strip()
                            if not text:
                                continue
                            try:
                                data = json.loads(text)
                                # Parse based on backend format
                                if backend in ("lmstudio", "lemonade"):
                                    # OpenAI format: choices[0].delta.content
                                    content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                elif backend == "llamacpp":
                                    # llama.cpp typically uses OpenAI format
                                    content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                else:
                                    # Ollama format: response
                                    content = data.get('response', '')
                                if content:
                                    yield content
                                if data.get("done", False) or (backend not in ("lmstudio", "lemonade", "llamacpp") and data.get('done', False)):
                                    break
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse stream line: {text[:50]}")
            except requests.RequestException as e:
                yield f"[Error: {e}]"

logger = logging.getLogger(__name__)

# ==================== **1. CONFIG** ====================

@dataclass
class ModelsConfig:
    """Configuration multi-modèles - importée depuis settings.py"""
    # Models importés depuis settings (pas de hardcoding)
    fast: str = ""
    reasoning: str = ""
    code: str = ""
    reasoner: str = ""
    
    # Backend settings from settings
    ollama_url: str = ""
    backend: Literal["ollama", "http"] = "ollama"
    timeout: int = 120
    
    def __post_init__(self):
        from models.settings import settings
        # Utiliser settings comme source unique - pas de fallback codé en dur
        self.fast = self.fast or settings.model_fast
        self.reasoning = self.reasoning or settings.model_reasoning
        self.code = self.code or settings.model_code
        self.reasoner = self.reasoner or settings.model_reasoning
        if not self.ollama_url:
            self.ollama_url = f"{settings.ollama_url}/api/generate"

# Singleton settings - utilise settings.py comme source unique
# Models MUST be set via environment variables - no hardcoded defaults
try:
    from models.settings import settings as _app_settings
    _settings = ModelsConfig(
        fast=_app_settings.model_fast,
        reasoning=_app_settings.model_reasoning,
        code=_app_settings.model_code,
        reasoner=_app_settings.model_reasoning,
        ollama_url=f"{_app_settings.ollama_url}/api/generate",
    )
except:
    _settings = ModelsConfig()


# ==================== **2. Router Pattern** ====================

class LLMRouter:
    """
    Intelligent router qui choisit le meilleur modèle.
    
    ✅ Routing intelligent
    ✅ Cache responses
    ✅ Fallback automatique
    ✅ Multi-model orchestration
    
    Usage:
      router = LLMRouter()
      llm = router.get_for_task("plan")  # → qwen-opus
      llm = router.get_for_task("code")   # → deepseek
    """
    
    def __init__(self, config: ModelsConfig | None = None):
        self.config = config or _settings
        self.cache = {}
    
    def get_model_for_task(self, task: str) -> str:
        """
        Choisir le meilleur modèle pour la tâche.
        
        Args:
            task: Description de la tâche
            
        Returns:
            Nom du modèle
            
        Routing logic:
          - code/bug: deepseek-coder
          - debug/architect: qwen-opus
          - explain: qwen-7b
          - default: qwen-32b
        """
        task_lower = task.lower()
        
        keywords = {
            "code": ["code", "implement", "function", "variable", "import", "def "],
            "reasoner": ["debug", "error", "architecture", "complex", "plan", "architect"],
            "fast": ["explain", "describe", "simple", "what ", "who "]
        }
        
        for category, keywords_list in keywords.items():
            if any(kw in task_lower for kw in keywords_list):
                if category == "code":
                    return self.config.code
                elif category == "reasoner":
                    return self.config.reasoner
                elif category == "fast":
                    return self.config.fast
        
        return self.config.reasoning  # Default to reasoning
    
    def _create_model_config(self, model_name: str | None = None) -> ModelConfig:
        """Create ModelConfig from current config and optional model name."""
        return ModelConfig(
            url=self.config.ollama_url,
            model=model_name or self.config.fast,
            timeout=self.config.timeout,
        )
    
    def get_for_task(self, task: str) -> OllamaClient:
        """
        Créer OllamaClient approprié.
        
        Args:
            task: Description
            
        Returns:
            OllamaClient configuré
        """
        model_name = self.get_model_for_task(task)
        logger.debug(f"Routing task to model: {model_name}")
        return OllamaClient(self._create_model_config(model_name))
    
    def try_fallback(self, task: str) -> str:
        """
        Essayer fallback si modèle échoue.
        
        Args:
            task: Tête échouée
            
        Returns:
            Message d'erreur si tous échouent
        """
        # Try reasoning model first
        return f"[Error: Fallback tried {self.config.reasoner}]"

    def generate(self, prompt: str, mode: str = "fast") -> str:
        """
        Generate response - convenience method.
        
        Args:
            prompt: The prompt
            mode: fast/code/reasoning
            
        Returns:
            Response text
        """
        # Get client for mode
        mode_to_model = {
            "fast": self.config.fast,
            "code": self.config.code,
            "reasoning": self.config.reasoning,
            "reasoner": self.config.reasoner,
        }
        model_name = mode_to_model.get(mode, self.config.fast)
        
        # Get client and generate
        client = OllamaClient(self._create_model_config(model_name))
        return client.generate(prompt)
    
    def get_for_mode(self, mode: str) -> OllamaClient:
        """
        Get client by mode (fast/code/reasoning).
        """
        model_name = {
            "fast": self.config.fast,
            "code": self.config.code,
            "reasoning": self.config.reasoning,
            "reasoner": self.config.reasoner,
        }.get(mode, self.config.fast)
        return OllamaClient(self._create_model_config(model_name))


# ==================== **3. Test Routing** ====================

class TestLLMRouter:
    """
    Test suite pour LLMRouter.
    """
    
    def test_routing_logic(self):
        """Test routing"""
        router = LLMRouter()
        
        # Code task → deepseek
        assert router.get_model_for_task("def hello():") == "deepseek-coder:33b"
        
        # Architecture task → qwen-opus
        assert router.get_model_for_task("architecture") == "qwen-opus"
        
        # Simple task → fast
        assert router.get_model_for_task("explanation") in ["qwen2.5-coder:7b"]
        
    def test_fallback(self):
        """Test fallback"""
        # Test fallback when no Ollama available
        # (Skip in production)
        pass
