import copy
import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Note: Configure logging.basicConfig(...) before importing this module
# to see logs from settings.py
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent

# Load .env file relative to PROJECT_ROOT
ENV_FILE = PROJECT_ROOT / ".env"
LOAD_DOTENV = ENV_FILE.exists()
if LOAD_DOTENV:
    load_dotenv(ENV_FILE)
    logger.debug(f"[settings] Loaded .env from {ENV_FILE}")
else:
    logger.debug(f"[settings] No .env file found at {ENV_FILE}")

# Paths - relative to PROJECT_ROOT
WORKSPACE = PROJECT_ROOT / os.getenv("WORKSPACE", "workspace")
TEMPLATES = PROJECT_ROOT / "templates"


def _parse_bool(value: str | None, default: bool = False) -> bool:
    """Parse boolean from environment variable."""
    if value is None:
        return default
    lower = value.lower()
    if lower in ("true", "1", "yes", "on"):
        return True
    if lower in ("false", "0", "no", "off"):
        return False
    return default


# LLM Backend Settings
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LEMONADE_URL = os.getenv("LEMONADE_URL", "http://localhost:13305")
LLAMACPP_URL = os.getenv("LLAMACPP_URL", "http://localhost:8080")
LMSTUDIO_URL = os.getenv("LMSTUDIO_URL", "http://localhost:1234")

# Model Settings
MODEL_FAST = os.getenv("MODEL_FAST", "qwen2.5-coder:32b")
MODEL_REASONING = os.getenv("MODEL_REASONING", "qwen-opus")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 30))

# Executor Settings
EXECUTOR_TIMEOUT = int(os.getenv("EXECUTOR_TIMEOUT", 60))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# HF_TOKEN should be loaded carefully (see memory.py or .env)
# DO NOT hardcode in this file!

# Backend configuration (deep copy to prevent mutation)
_BACKENDS_TEMPLATE = {
    "ollama": {
        "url": OLLAMA_URL,
        "enabled": _parse_bool(os.getenv("OLLAMA_ENABLED"), True),
        "models_endpoint": "/api/tags",
    },
    "lemonade": {
        "url": LEMONADE_URL,
        "enabled": _parse_bool(os.getenv("LEMONADE_ENABLED"), True),
        "models_endpoint": "/api/v1/models",
    },
    "llamacpp": {
        "url": LLAMACPP_URL,
        "enabled": _parse_bool(os.getenv("LLAMACPP_ENABLED"), False),
        "models_endpoint": "/props",
    },
    "lmstudio": {
        "url": LMSTUDIO_URL,
        "enabled": _parse_bool(os.getenv("LMSTUDIO_ENABLED"), False),
        "models_endpoint": "/api/v1/models",
    },
}

# Reasoning keywords for smart model selection
REASONING_KEYWORDS = frozenset(["error", "debug", "optimize", "architecture", "complex", "plan", "architect"])


@dataclass(frozen=True)
class Settings:
    """Immutable configuration singleton."""
    ollama_url: str = OLLAMA_URL
    lemonade_url: str = LEMONADE_URL
    llamacpp_url: str = LLAMACPP_URL
    lmstudio_url: str = LMSTUDIO_URL
    model_fast: str = MODEL_FAST
    model_reasoning: str = MODEL_REASONING
    llm_timeout: int = LLM_TIMEOUT
    executor_timeout: int = EXECUTOR_TIMEOUT
    log_level: str = LOG_LEVEL
    workspace: Path = WORKSPACE
    load_dotenv: bool = LOAD_DOTENV
    backends: dict = field(default_factory=lambda: copy.deepcopy(_BACKENDS_TEMPLATE))
    
    def get_model_for_task(self, task_type: str) -> str:
        """Smart model selection based on task type."""
        task_lower = task_type.lower()
        
        if task_lower == "fast":
            return self.model_fast
        elif task_lower == "reasoning":
            return self.model_reasoning
        elif any(kw in task_lower for kw in REASONING_KEYWORDS):
            return self.model_reasoning
        return self.model_fast
    
    def get_workspace_str(self) -> str:
        """Get workspace as string for external I/O."""
        return str(self.workspace)


# True singleton pattern
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Public API
settings = get_settings()


def get_model_for_task(task_type: str) -> str:
    """Smart model selection based on task type (delegates to singleton)."""
    return settings.get_model_for_task(task_type)