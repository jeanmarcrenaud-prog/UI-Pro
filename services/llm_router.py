# services/llm_router.py - Advanced LLM Router
#
# Intelligent routing with:
# - Task-based model selection
# - Context window awareness
# - Load balancing across models
# - Cost optimization

import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task type classification"""
    CODE = "code"
    REASONING = "reasoning"
    FAST = "fast"
    CREATIVE = "creative"
    ANALYSIS = "analysis"


@dataclass
class RouterConfig:
    """Router configuration"""
    default_model: str = "gemma4:latest"
    max_context_tokens: int = 8192
    enable_cost_optimization: bool = True
    enable_load_balancing: bool = False


class LLMRouter:
    """
    Advanced LLM Router with intelligent task matching.
    
    Features:
    - Task classification (code/reasoning/fast/creative)
    - Context-aware routing
    - Model capability matching
    - Fallback chains
    """
    
    # Task keywords for classification
    TASK_KEYWORDS = {
        TaskType.CODE: [
            "code", "implement", "function", "class ", "def ", "import ",
            "api", "endpoint", "database", "sql", "query", "debug", "bug"
        ],
        TaskType.REASONING: [
            "reason", "why", "how", "explain", "think", "analyze",
            "architecture", "design", "plan", "strategy", "compare"
        ],
        TaskType.CREATIVE: [
            "create", "write", "story", "generate", "creative", "draft",
            "content", "narrative", "poem", "script"
        ],
        TaskType.ANALYSIS: [
            "analyze", "review", "evaluate", "assess", "audit",
            "optimize", "improve", "refactor", "debug"
        ],
        TaskType.FAST: [
            "what", "who", "when", "where", "list", "simple",
            "quick", "brief", "summary", "explain"
        ],
    }
    
    # Model capabilities mapping
    MODEL_CAPABILITIES = {
        "gemma4:latest": {
            "strengths": [TaskType.CODE, TaskType.REASONING, TaskType.FAST],
            "max_context": 8192,
            "speed": "fast",
        },
        "gemma4:e4b": {
            "strengths": [TaskType.CODE, TaskType.FAST],
            "max_context": 4096,
            "speed": "very_fast",
        },
        "lfm2:latest": {
            "strengths": [TaskType.REASONING, TaskType.ANALYSIS],
            "max_context": 16384,
            "speed": "medium",
        },
    }
    
    # Default fallback chains
    FALLBACK_CHAINS = {
        TaskType.CODE: ["gemma4:latest", "gemma4:e4b"],
        TaskType.REASONING: ["gemma4:latest", "lfm2:latest"],
        TaskType.CREATIVE: ["gemma4:latest", "lfm2:latest"],
        TaskType.ANALYSIS: ["lfm2:latest", "gemma4:latest"],
        TaskType.FAST: ["gemma4:e4b", "gemma4:latest"],
    }
    
    def __init__(self, config: RouterConfig = None):
        self.config = config or RouterConfig()
        self._call_history: List[Dict] = []
    
    def classify_task(self, prompt: str = None, messages: List[Dict] = None) -> TaskType:
        """
        Classify task based on prompt OR full messages history.
        
        Args:
            prompt: Direct prompt string
            messages: Chat messages [{"role": "user", "content": "..."}]
            
        Returns:
            TaskType: Classified task type
        """
        # Use messages if provided, otherwise use prompt
        if messages:
            # Combine all user messages for analysis
            content_parts = []
            for msg in messages:
                if msg.get("role") == "user" and msg.get("content"):
                    content_parts.append(msg["content"].lower())
            prompt_lower = " ".join(content_parts)
        elif prompt:
            prompt_lower = prompt.lower()
        else:
            return TaskType.FAST
        
        # Score each task type
        scores = {tt: 0 for tt in TaskType}
        
        for task_type, keywords in self.TASK_KEYWORDS.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    scores[task_type] += 1
        
        # Return highest scoring type
        max_score = max(scores.values())
        if max_score == 0:
            return TaskType.FAST  # Default
        
        for task_type, score in scores.items():
            if score == max_score:
                return task_type
        
        return TaskType.FAST
    
    def select_model(
        self, 
        task_type: TaskType = None,
        prompt: str = None,
        messages: List[Dict] = None,
        context_length: int = None
    ) -> str:
        """
        Select best model for task.
        
        Args:
            task_type: Task type (auto-detected if not provided)
            prompt: User prompt (used for auto-detection)
            messages: Full messages history
            context_length: Required context length
            
        Returns:
            str: Selected model name
        """
        # Auto-detect task type if not provided
        if task_type is None:
            task_type = self.classify_task(prompt, messages)
        
        # Get fallback chain for task type
        chain = self.FALLBACK_CHAINS.get(task_type, [self.config.default_model])
        
        # Filter by context requirements
        if context_length:
            for model in chain:
                caps = self.MODEL_CAPABILITIES.get(model, {})
                if caps.get("max_context", 8192) >= context_length:
                    return model
        
        # Return first available in chain
        return chain[0] if chain else self.config.default_model
    
    def get_fallback_chain(self, task_type: TaskType) -> List[str]:
        """Get fallback chain for task type"""
        return self.FALLBACK_CHAINS.get(task_type, [self.config.default_model])
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (~4 chars per token)"""
        return len(text) // 4
    
    def route(
        self,
        prompt: str = None,
        messages: List[Dict] = None,
        mode: str = None,
        context_length: int = None
    ) -> Dict[str, Any]:
        """
        Full routing decision with metadata.
        
        Args:
            prompt: Direct prompt string
            messages: Chat messages [{"role": "user", "content": "..."}]
            mode: Explicit mode override
            context_length: Required context length
        
        Returns:
            dict: {
                "model": str,
                "task_type": TaskType,
                "fallback_chain": List[str],
                "estimated_tokens": int
            }
        """
        # Map mode to task type
        task_type = None
        if mode:
            mode_map = {
                "fast": TaskType.FAST,
                "code": TaskType.CODE,
                "reasoning": TaskType.REASONING,
                "creative": TaskType.CREATIVE,
                "analysis": TaskType.ANALYSIS,
            }
            task_type = mode_map.get(mode.lower())
        
        # Detect task type from messages/prompt
        if task_type is None:
            task_type = self.classify_task(prompt, messages)
        
        # Calculate total content for token estimation
        total_content = ""
        if messages:
            for msg in messages:
                if msg.get("content"):
                    total_content += msg["content"] + " "
        elif prompt:
            total_content = prompt
        
        est_tokens = self.estimate_tokens(total_content) if total_content else 0
        
        # Select model
        model = self.select_model(task_type, messages=messages, context_length=context_length)
        
        return {
            "model": model,
            "task_type": task_type,
            "fallback_chain": self.get_fallback_chain(task_type),
            "estimated_tokens": est_tokens,
            "context_needed": est_tokens > self.config.max_context_tokens,
        }
    
    def record_call(self, model: str, task_type: TaskType, latency_ms: float, success: bool):
        """Record call for metrics"""
        self._call_history.append({
            "model": model,
            "task_type": task_type,
            "latency_ms": latency_ms,
            "success": success,
            "timestamp": datetime.now(),
        })
        
        # Keep last 100
        if len(self._call_history) > 100:
            self._call_history = self._call_history[-100:]


# Import datetime for record_call
from datetime import datetime


# Singleton instance
_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    """Get singleton router"""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


__all__ = ["LLMRouter", "TaskType", "RouterConfig", "get_llm_router"]