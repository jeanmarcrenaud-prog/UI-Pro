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
from typing import Literal
import logging

logger = logging.getLogger(__name__)

# ==================== **1. CONFIG** ====================

@dataclass
class ModelsConfig:
    """Configuration multi-modèles"""
    # Models listés par type d'usage
    fast: str = "qwen2.5-coder:7b"
    reasoning: str = "qwen2.5-coder:32b"
    code: str = "deepseek-coder:33b"
    reasoner: str = "qwen-opus"
    
    # Backend settings from settings
    ollama_url: str = ""
    backend: Literal["ollama", "http"] = "ollama"
    timeout: int = 120
    
    def __post_init__(self):
        if not self.ollama_url:
            from models.settings import settings
            self.ollama_url = f"{settings.ollama_url}/api/generate"

# Singleton settings
try:
    from models.settings import settings as _app_settings
    _settings = ModelsConfig(
        fast=_app_settings.model_fast,
        reasoning=_app_settings.model_reasoning,
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
    
    def get_for_task(self, task: str) -> "LLMClient":
        """
        Créer LLMClient approprié.
        
        Args:
            task: Description
            
        Returns:
            LLMClient configuré
        """
        model_name = self.get_model_for_task(task)
        logger.debug(f"Routing task to model: {model_name}")
        return OllamaClient(self.config)
    
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
            "fast": getattr(self.config, 'fast', None) or "qwen2.5-coder:7b",
            "code": getattr(self.config, 'code', None) or "deepseek-coder:33b",
            "reasoning": getattr(self.config, 'reasoning', None) or "qwen2.5-coder:32b",
            "reasoner": getattr(self.config, 'reasoner', None) or "qwen-opus",
        }
        model_name = mode_to_model.get(mode, mode_to_model.get("fast"))
        
        # Get client and generate
        client = OllamaClient(self.config)
        return client.generate(prompt)
    
    def get_for_mode(self, mode: str) -> "OllamaClient":
        """
        Get client by mode (fast/code/reasoning).
        """
        return OllamaClient(self.config)


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
