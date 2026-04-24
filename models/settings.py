"""
models/settings.py - Unified Configuration
#
# Role: Single source of truth for all settings (YAML + env backends)
# Used by: All modules requiring configuration
#
# NOTE:

NOTE:
- YAML config is intended for application-level settings (app, api, memory, dashboard).
- LLM and backend settings are managed exclusively via environment variables.
- Sensitive settings (API keys) MUST be set via environment variables only.
"""

import copy
import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import yaml

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


def _load_yaml_config() -> Dict[str, Any]:
    """Load config from YAML file"""
    config_file = PROJECT_ROOT / "config.yaml"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load config.yaml: {e}")
            return {}
    return {}


# ========================
# Load base config from YAML
# ========================
_YAML_CONFIG = _load_yaml_config()


# ========================
# LLM Backend Settings
# ========================
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


# ========================
# Backend configuration
# ========================
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


# ========================
# Unified Settings class
# ========================
@dataclass(frozen=True)
class Settings:
    """Immutable configuration singleton - unified source of truth."""
    # Paths
    project_root: Path = PROJECT_ROOT
    workspace: Path = WORKSPACE
    templates: Path = TEMPLATES
    
    # Backend URLs
    ollama_url: str = OLLAMA_URL
    lemonade_url: str = LEMONADE_URL
    llamacpp_url: str = LLAMACPP_URL
    lmstudio_url: str = LMSTUDIO_URL
    
    # Model settings
    model_fast: str = MODEL_FAST
    model_reasoning: str = MODEL_REASONING
    llm_timeout: int = LLM_TIMEOUT
    
    # Executor settings
    executor_timeout: int = EXECUTOR_TIMEOUT
    
    # Logging
    log_level: str = LOG_LEVEL
    
    # YAML-based settings (for backward compatibility)
    app_name: str = "UI-Pro"
    version: str = "1.0.0"
    debug: bool = False
    api_host: str = "localhost"
    api_port: int = 8000
    api_key: str = ""
    dashboard_port: int = 7860
    memory_enabled: bool = True
    memory_limit_mb: int = 512
    
    # Config
    load_dotenv: bool = LOAD_DOTENV
    backends: dict = field(default_factory=lambda: copy.deepcopy(_BACKENDS_TEMPLATE))
    
    def __post_init__(self):
        # Override YAML-based settings if present in config
        app_config = _YAML_CONFIG.get("app", {})
        llm_config = _YAML_CONFIG.get("llm", {})
        executor_config = _YAML_CONFIG.get("executor", {})
        memory_config = _YAML_CONFIG.get("memory", {})
        logging_config = _YAML_CONFIG.get("logging", {})
        api_config = _YAML_CONFIG.get("api", {})
        dashboard_config = _YAML_CONFIG.get("dashboard", {})
        
        # Override using object.__setattr__ (frozen dataclass)
        object.__setattr__(self, 'app_name', os.getenv("APP_NAME", app_config.get("name", self.app_name)))
        object.__setattr__(self, 'version', os.getenv("VERSION", app_config.get("version", self.version)))
        object.__setattr__(self, 'debug', _parse_bool(os.getenv("DEBUG"), app_config.get("debug", self.debug)))
        object.__setattr__(self, 'api_host', os.getenv("API_HOST", api_config.get("host", self.api_host)))
        object.__setattr__(self, 'api_port', int(os.getenv("API_PORT", api_config.get("port", self.api_port))))
        # Security: api_key MUST come from env only (never from YAML)
        api_key_env = os.getenv("API_KEY")
        if api_key_env:
            object.__setattr__(self, 'api_key', api_key_env)
        object.__setattr__(self, 'dashboard_port', int(os.getenv("DASHBOARD_PORT", dashboard_config.get("port", self.dashboard_port))))
        object.__setattr__(self, 'memory_enabled', _parse_bool(os.getenv("MEMORY_ENABLED"), memory_config.get("enabled", self.memory_enabled)))
        object.__setattr__(self, 'memory_limit_mb', int(os.getenv("MEMORY_LIMIT_MB", memory_config.get("limit_mb", self.memory_limit_mb))))
    
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
    
    def validate(self) -> tuple[bool, list[str]]:
        """Validate configuration. Returns (is_valid, list_of_errors)."""
        errors = []
        
        if self.api_port <= 0 or self.api_port > 65535:
            errors.append(f"Invalid api_port: {self.api_port}")
        
        if self.dashboard_port <= 0 or self.dashboard_port > 65535:
            errors.append(f"Invalid dashboard_port: {self.dashboard_port}")
        
        # Check workspace exists or can be created
        if not self.workspace.exists():
            try:
                self.workspace.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create workspace {self.workspace}: {e}")
        
        return (len(errors) == 0, errors)


# True singleton pattern
_settings: Optional[Settings] = None


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


# Backward compatibility - module-level constants
BACKENDS = _BACKENDS_TEMPLATE