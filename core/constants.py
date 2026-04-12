# core/constants.py - Constants centralisées pour UI-Pro

# ==================== WebSocket Events ====================

class WSEvent:
    """Types d'événements WebSocket"""
    TOKEN = "token"
    STEP = "step"
    TOOL = "tool"
    DONE = "done"
    ERROR = "error"


# ==================== Agent Steps ====================

class AgentStep:
    """Étapes de l'agent"""
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"


# ==================== Error Codes ====================

class ErrorCode:
    """Codes d'erreur métier"""
    INVALID_INPUT = "INVALID_INPUT"
    LLM_ERROR = "LLM_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    MEMORY_ERROR = "MEMORY_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    SANDBOX_ERROR = "SANDBOX_ERROR"


# ==================== Config Keys ====================

class ConfigKey:
    """Clés de configuration"""
    OLLAMA_URL = "ollama_url"
    MODEL_FAST = "model_fast"
    MODEL_REASONING = "model_reasoning"
    LLM_TIMEOUT = "llm_timeout"
    EXECUTOR_TIMEOUT = "executor_timeout"
    MEMORY_LIMIT_MB = "memory_limit_mb"
    LOG_LEVEL = "log_level"


# ==================== Model Names ====================

# Modèles disponibles sur Ollama
AVAILABLE_MODELS = [
    "qwen3.5:9b",
    "qwen3.5:0.8b",
    "gemma4:latest",
    "minimax-m2:cloud",
]