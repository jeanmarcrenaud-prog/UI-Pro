"""
settings.py

Configuration externalisée pour le projet ui-pro.
Charge depuis .env file ou environnement variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
LOAD_DOTENV = Path(".env").exists()
if LOAD_DOTENV:
    load_dotenv(".env")

# Paths
PROJECT_ROOT = Path(__file__).parent
WORKSPACE = Path(os.getenv("WORKSPACE", "workspace"))
TEMPLATES = Path("templates")

# LLM Settings
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_FAST = os.getenv("MODEL_FAST", "qwen3.5:9b")
MODEL_REASONING = os.getenv("MODEL_REASONING", "qwen3.5:9b")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 30))

# Executor Settings
EXECUTOR_TIMEOUT = int(os.getenv("EXECUTOR_TIMEOUT", 60))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# HF_TOKEN should be loaded carefully (see memory.py or .env)
# DO NOT hardcode in this file!

class Settings:
    """Configuration dictionary."""
    ollama_url = OLLAMA_URL
    model_fast = MODEL_FAST
    model_reasoning = MODEL_REASONING
    llm_timeout = LLM_TIMEOUT
    executor_timeout = EXECUTOR_TIMEOUT
    log_level = LOG_LEVEL
    workspace = str(WORKSPACE)
    load_dotenv = LOAD_DOTENV

    def get_model_for_task(self, task_type: str) -> str:
        """Smart model selection based on task type."""
        if task_type.lower() == "fast":
            return self.model_fast
        elif task_type.lower() == "reasoning":
            return self.model_reasoning
        elif task_type.lower() in ["error", "debug", "optimize", "architecture", "complex", "plan", "architect"]:
            return self.model_reasoning
        return self.model_fast

# Singleton instance
_settings: Settings = None

def get_settings() -> Settings:
    """Get singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

settings = get_settings()

def get_model_for_task(task_type: str) -> str:
    """Smart model selection based on task type."""
    reasoning_keywords = ["error", "debug", "optimize", "architecture", "complex", "plan", "architect"]
    task_lower = task_type.lower()
    
    if any(keyword in task_lower for keyword in reasoning_keywords):
        return _settings.model_reasoning
    return _settings.model_fast
