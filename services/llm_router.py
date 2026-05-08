# services/llm_router.py - Advanced LLM Router
#
# Intelligent routing with task-based model selection
# Integrated with models.settings as single source of truth

import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from models.settings import settings

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task type classification"""
    FAST = "fast"
    CODE = "code"
    REASONING = "reasoning"
    CREATIVE = "creative"
    ANALYSIS = "analysis"


@dataclass
class RouterConfig:
    """Router configuration"""
    max_context_tokens: int = 8192
    enable_cost_optimization: bool = True
    enable_load_balancing: bool = False


class LLMRouter:
    """
    Production-ready LLM Router integrated with settings.py
    """
    
    # Task keywords for classification
    TASK_KEYWORDS = {
        TaskType.CODE: [
            "code", "implement", "function", "class ", "def ", "import ",
            "api", "endpoint", "sql", "query", "bug", "fix", "refactor"
        ],
        TaskType.REASONING: [
            "why", "how", "explain", "analyze", "architecture", "design",
            "plan", "strategy", "compare", "reason", "optimize"
        ],
        TaskType.CREATIVE: [
            "create", "write", "story", "generate", "draft", "poem", "script", "content"
        ],
        TaskType.ANALYSIS: [
            "analyze", "review", "evaluate", "assess", "audit", "improve"
        ],
        TaskType.FAST: [
            "what", "who", "when", "where", "list", "simple", "quick", "brief", "summary"
        ],
    }

    def __init__(self, config: Optional[RouterConfig] = None):
        self.config = config or RouterConfig()
        self._call_history: List[Dict] = []

        # Load models from central settings (Single Source of Truth)
        self.models = {
            TaskType.FAST: settings.model_fast,
            TaskType.REASONING: settings.model_reasoning,
            TaskType.CODE: settings.model_code,
            TaskType.ANALYSIS: settings.model_reasoning,  # usually same as reasoning
            TaskType.CREATIVE: settings.model_reasoning,
        }

    def classify_task(self, prompt: Optional[str] = None, messages: Optional[List[Dict]] = None) -> TaskType:
        """Classify task based on content."""
        if messages:
            content = " ".join(
                msg.get("content", "") for msg in messages 
                if msg.get("role") == "user"
            ).lower()
        elif prompt:
            content = prompt.lower()
        else:
            return TaskType.FAST

        scores = {task: 0 for task in TaskType}
        
        for task_type, keywords in self.TASK_KEYWORDS.items():
            scores[task_type] = sum(1 for kw in keywords if kw in content)

        # Return highest scoring task type
        return max(scores.items(), key=lambda x: x[1])[0]

    def select_model(
        self,
        task_type: Optional[TaskType] = None,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict]] = None,
        context_length: Optional[int] = None,
    ) -> str:
        """Select best model for the task."""
        if task_type is None:
            task_type = self.classify_task(prompt, messages)

        # Return configured model for this task type
        model = self.models.get(task_type)

        # Fallback chain
        if not model or model.strip() == "":
            fallback_order = [TaskType.REASONING, TaskType.FAST, TaskType.CODE]
            for fallback in fallback_order:
                model = self.models.get(fallback)
                if model and model.strip():
                    break

        return model or settings.model_fast

    def route(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict]] = None,
        mode: Optional[str] = None,
        context_length: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Main routing method.
        Returns rich metadata for observability.
        """
        if mode:
            mode = mode.lower()
            task_type = {
                "fast": TaskType.FAST,
                "code": TaskType.CODE,
                "reasoning": TaskType.REASONING,
                "creative": TaskType.CREATIVE,
                "analysis": TaskType.ANALYSIS,
            }.get(mode, None)
        else:
            task_type = self.classify_task(prompt, messages)

        model = self.select_model(task_type, prompt, messages, context_length)

        # Rough token estimation
        text = prompt or ""
        if messages:
            text = " ".join(msg.get("content", "") for msg in messages if msg.get("content"))
        estimated_tokens = len(text) // 4

        return {
            "model": model,
            "task_type": task_type.value if task_type else "unknown",
            "estimated_tokens": estimated_tokens,
            "exceeds_context": estimated_tokens > self.config.max_context_tokens,
            "routing_method": "keyword+config",
            "confidence": 0.85,
        }

    def record_call(self, model: str, task_type: TaskType, latency_ms: float, success: bool):
        """Record usage for future analytics."""
        self._call_history.append({
            "model": model,
            "task_type": task_type.value if task_type else "unknown",
            "latency_ms": latency_ms,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        })

        if len(self._call_history) > 200:
            self._call_history = self._call_history[-200:]


# ======================== Singleton ========================

_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    """Get singleton router instance."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


__all__ = ["LLMRouter", "TaskType", "RouterConfig", "get_llm_router"]