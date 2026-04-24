# services/llm_router.py - Advanced LLM Router
#
# Role: Task-based model selection with cost/window optimization
# Used by: orchestrator for complex task routing

Contract:
    async select_model(task: TaskType, context_window?: int) -> ModelInfo
    async route(prompt: str, options?: RouteOptions) -> LLMResponse
    
DIFFERENT from llm/router.py (basic routing):
    - Task-based classification (CODE vs REASONING)
    - Context window awareness
    - Cost optimization
    
Dependencies:
    - llm/router.py for basic LLM calls
"""

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
    default_model: str = "qwen3.5:0.8b"
    max_context_tokens: int = 8192
    enable_cost_optimization: bool = True
    enable_load_balancing: bool = False


# Import datetime for record_call
from datetime import datetime
import json


class LLMRouter:
    """
    Advanced LLM Router with intelligent task matching.
    
    Features:
    - Scoring-based model selection (code/chat/reasoning)
    - LLM-based routing (decision via small model)
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
        "qwen3.5:0.8b": {
            "strengths": [TaskType.CODE, TaskType.REASONING, TaskType.FAST],
            "max_context": 4096,
            "speed": "fast",
        },
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
        TaskType.CODE: ["qwen3.5:0.8b", "gemma4:latest", "gemma4:e4b"],
        TaskType.REASONING: ["qwen3.5:0.8b", "gemma4:latest", "lfm2:latest"],
        TaskType.CREATIVE: ["qwen3.5:0.8b", "gemma4:latest", "lfm2:latest"],
        TaskType.ANALYSIS: ["lfm2:latest", "gemma4:latest"],
        TaskType.FAST: ["qwen3.5:0.8b", "gemma4:e4b", "gemma4:latest"],
    }
    
    # Model scoring functions (for scoring-based routing)
    MODEL_SCORING = {
        "qwen3.5:0.8b": {
            "code_score": 0.95,
            "chat_score": 0.9,
            "reasoning_score": 0.85,
        },
        "qwen2.5-coder:32b": {
            "code_score": 1.0,
            "chat_score": 0.7,
            "reasoning_score": 0.6,
        },
        "gemma4:latest": {
            "code_score": 0.9,
            "chat_score": 0.85,
            "reasoning_score": 0.9,
        },
        "gemma4:e4b": {
            "code_score": 0.7,
            "chat_score": 0.95,
            "reasoning_score": 0.7,
        },
        "lfm2:latest": {
            "code_score": 0.5,
            "chat_score": 0.8,
            "reasoning_score": 1.0,
        },
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
    
    # ===== Scoring-Based Routing =====
    
    def _get_task_category(self, messages: List[Dict] = None, prompt: str = None) -> str:
        """
        Determine primary task category for scoring.
        
        Returns: "code", "chat", or "reasoning"
        """
        content = ""
        if messages:
            for msg in messages[-3:]:
                if msg.get("content"):
                    content += msg["content"].lower() + " "
        elif prompt:
            content = prompt.lower()
        
        # Code indicators
        code_indicators = ["code", "implement", "function", "class", "def ", "import ",
                          "api", "debug", "bug", "error", "sql", "query"]
        # Reasoning indicators  
        reasoning_indicators = ["why", "how", "explain", "think", "analyze", "architecture",
                               "design", "plan", "strategy", "compare", "reason"]
        
        code_count = sum(1 for ind in code_indicators if ind in content)
        reasoning_count = sum(1 for ind in reasoning_indicators if ind in content)
        
        if code_count > reasoning_count and code_count >= 2:
            return "code"
        elif reasoning_count > code_count and reasoning_count >= 2:
            return "reasoning"
        else:
            return "chat"  # Default
    
    def score_models(self, messages: List[Dict] = None, prompt: str = None) -> Dict[str, float]:
        """
        Score all available models based on task.
        
        Args:
            messages: Chat messages for context
            prompt: Direct prompt
            
        Returns:
            Dict mapping model name to score
        """
        category = self._get_task_category(messages, prompt)
        
        # Map category to score key
        score_key_map = {
            "code": "code_score",
            "reasoning": "reasoning_score", 
            "chat": "chat_score"
        }
        score_key = score_key_map.get(category, "chat_score")
        
        scores = {}
        for model, scoring in self.MODEL_SCORING.items():
            scores[model] = scoring.get(score_key, 0.5)
        
        return scores
    
    def route_by_score(
        self,
        messages: List[Dict] = None,
        prompt: str = None,
        mode: str = None
    ) -> Dict[str, Any]:
        """
        Route using scoring system.
        
        This is a simpler alternative to LLM-based routing.
        
        Args:
            messages: Chat messages
            prompt: Direct prompt
            mode: Explicit mode override
            
        Returns:
            dict: Routing decision with scores
        """
        # Get scores
        scores = self.score_models(messages, prompt)
        
        # Apply mode filter if specified
        if mode:
            mode_task_type = {
                "code": TaskType.CODE,
                "reasoning": TaskType.REASONING,
                "fast": TaskType.FAST,
                "creative": TaskType.CREATIVE,
                "analysis": TaskType.ANALYSIS,
            }.get(mode.lower(), TaskType.FAST)
            
            # Filter models by capability
            filtered_scores = {}
            for model, score in scores.items():
                caps = self.MODEL_CAPABILITIES.get(model, {})
                if mode_task_type in caps.get("strengths", []):
                    filtered_scores[model] = score
            
            if filtered_scores:
                scores = filtered_scores
        
        # Get best model
        best_model = max(scores, key=scores.get)
        best_score = scores[best_model]
        
        # Determine task type
        category = self._get_task_category(messages, prompt)
        task_type_map = {
            "code": TaskType.CODE,
            "reasoning": TaskType.REASONING,
            "chat": TaskType.FAST,
        }
        
        return {
            "model": best_model,
            "task_type": task_type_map.get(category, TaskType.FAST),
            "fallback_chain": [best_model] + [m for m in scores.keys() if m != best_model],
            "scores": scores,
            "routing_method": "scoring",
            "confidence": best_score,
        }
    
    def route(
        self,
        prompt: str = None,
        messages: List[Dict] = None,
        mode: str = None,
        context_length: int = None,
        use_scoring: bool = True
    ) -> Dict[str, Any]:
        """
        Full routing decision with metadata.
        
        Args:
            prompt: Direct prompt string
            messages: Chat messages [{"role": "user", "content": "..."}]
            mode: Explicit mode override
            context_length: Required context length
            use_scoring: Use scoring-based routing (default True)
        
        Returns:
            dict: {
                "model": str,
                "task_type": TaskType,
                "fallback_chain": List[str],
                "estimated_tokens": int,
                "routing_method": str,
                "scores": Dict (if scoring)
            }
        """
        # Use scoring-based routing by default
        if use_scoring:
            return self.route_by_score(messages=messages, prompt=prompt, mode=mode)
        
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
            "routing_method": "keyword",
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
    
    # ===== LLM-based Routing =====
    
    def _llm_route(self, messages: List[Dict] = None, prompt: str = None) -> str:
        """
        Use LLM to decide which model to use.
        
        This is more accurate than keyword matching but slower.
        Use for complex decisions.
        """
        # Build prompt for model selection
        content = ""
        if messages:
            for msg in messages[-3:]:  # Last 3 messages
                content += f"{msg.get('role')}: {msg.get('content', '')}\n"
        elif prompt:
            content = prompt
        
        selection_prompt = f"""You are a model routing system. Decide which model to use.

Available models and their strengths:
{self._format_model_descriptions()}

Conversation:
{content}

Respond ONLY with JSON:
{{"model": "model_name", "reasoning": "why you chose this"}}
"""
        
        try:
            # Use fast model for routing decision
            from .model_service import get_model_service
            llm = get_model_service()
            response = llm.generate(selection_prompt, mode="fast")
            
            # Parse response
            result = json.loads(response)
            return result.get("model", self.config.default_model)
            
        except Exception as e:
            logger.warning(f"LLM routing failed: {e}, falling back to scoring")
            return None
    
    def _format_model_descriptions(self) -> str:
        """Format model descriptions for LLM prompt"""
        lines = []
        for model, scoring in self.MODEL_SCORING.items():
            strengths = []
            if scoring.get("code_score", 0) > 0.7:
                strengths.append("code")
            if scoring.get("chat_score", 0) > 0.7:
                strengths.append("chat")
            if scoring.get("reasoning_score", 0) > 0.7:
                strengths.append("reasoning")
            lines.append(f"- {model}: {'/'.join(strengths) if strengths else 'general purpose'}")
        return "\n".join(lines)
    
    def route_with_llm(
        self,
        messages: List[Dict] = None,
        prompt: str = None,
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        Route with optional LLM-based decision.
        
        Args:
            messages: Chat messages
            prompt: Direct prompt
            use_llm: Force LLM-based routing
            
        Returns:
            dict: Routing decision
        """
        # Use LLM if requested or for complex cases
        if use_llm or (messages and len(messages) > 5):
            model = self._llm_route(messages, prompt)
            if model:
                return {
                    "model": model,
                    "task_type": TaskType.FAST,  # LLM decides
                    "fallback_chain": self.get_fallback_chain(TaskType.FAST),
                    "estimated_tokens": self.estimate_tokens(prompt or ""),
                    "routing_method": "llm"
                }
        
        # Fall back to scoring-based
        return self.route(messages=messages, prompt=prompt)


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