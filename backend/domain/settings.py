"""
backend/domain/settings.py - Unified Configuration

Role: Single source of truth for all settings (YAML + env backends)

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

# Paths - use parents[3] to go from backend/domain/ to project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]

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

# Model Settings - MUST be set via environment variables!
# No hardcoded defaults - models are dynamically detected via /api/tags
MODEL_FAST = os.getenv("MODEL_FAST") or ""  # Required - no default
MODEL_REASONING = os.getenv("MODEL_REASONING") or ""  # Required - no default
MODEL_CODE = os.getenv("MODEL_CODE") or ""  # Required - no default
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 120))  # 120s for reasoning/code models

# Executor Settings
EXECUTOR_TIMEOUT = int(os.getenv("EXECUTOR_TIMEOUT", 60))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# HF_TOKEN should be loaded carefully (see memory.py or .env)
# DO NOT hardcode in this file!


# ========================
# Backend configuration (inline in Settings.backends field)
# ========================

# Reasoning keywords for smart model selection
REASONING_KEYWORDS = frozenset(["error", "debug", "optimize", "architecture", "complex", "plan", "architect"])


# ========================
# Unified Settings class
# ========================
@dataclass(kw_only=True)
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
    model_code: str = MODEL_CODE
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
    backends: dict = field(default_factory=lambda: {
        "ollama": {"url": OLLAMA_URL, "enabled": True, "models_endpoint": "/api/tags"},
        "lemonade": {"url": LEMONADE_URL, "enabled": True, "models_endpoint": "/api/v1/models"},
        "llamacpp": {"url": LLAMACPP_URL, "enabled": False, "models_endpoint": "/props"},
        "lmstudio": {"url": LMSTUDIO_URL, "enabled": True, "models_endpoint": "/api/v1/models"},
    })

    def __new__(cls):
        """Singleton pattern - return existing instance if available."""
        if hasattr(cls, '_instance'):
            return cls._instance
        instance = super().__new__(cls)
        cls._instance = instance
        return instance

    def __init__(self, **kwargs):
        """Custom init to apply env/yaml overrides without object.__setattr__."""
        # Get YAML config
        yaml_app = _YAML_CONFIG.get("app", {})
        yaml_api = _YAML_CONFIG.get("api", {})
        yaml_memory = _YAML_CONFIG.get("memory", {})

        # Apply overrides (env takes priority over yaml)
        self.app_name = os.getenv("APP_NAME", yaml_app.get("name", self.app_name))
        self.version = os.getenv("VERSION", yaml_app.get("version", self.version))
        self.debug = _parse_bool(os.getenv("DEBUG"), yaml_app.get("debug", self.debug))
        self.api_host = os.getenv("API_HOST", yaml_api.get("host", self.api_host))
        self.api_port = int(os.getenv("API_PORT", yaml_api.get("port", self.api_port)))
        # Security: api_key MUST come from env only
        api_key_env = os.getenv("API_KEY")
        if api_key_env:
            self.api_key = api_key_env
        self.dashboard_port = int(os.getenv("DASHBOARD_PORT", yaml_api.get("dashboard_port", self.dashboard_port)))
        self.memory_enabled = _parse_bool(os.getenv("MEMORY_ENABLED"), yaml_memory.get("enabled", self.memory_enabled))
        self.memory_limit_mb = int(os.getenv("MEMORY_LIMIT_MB", yaml_memory.get("limit_mb", self.memory_limit_mb)))
    
    def get_model_for_task(self, task: str) -> str:
        """
        Simple model selection for basic task types.
        Complex keyword-based routing is handled by LLMRouter.
        
        Args:
            task: Task type ("fast", "reasoning", "code") or natural language
        
        Returns:
            Model name for the task
        """
        task_lower = task.lower().strip()
        
        # Simple mode selection (for backward compatibility)
        # Complex keyword-based routing is handled by LLMRouter only
        if task_lower == "fast":
            return self.model_fast
        if task_lower in ("reasoning", "reasoner"):
            return self.model_reasoning
        if task_lower == "code":
            return self.model_code
        
        # Default to fast for unknown simple tasks
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
        
        # Validate model configuration (required for LLM operations)
        if not self.model_fast or self.model_fast == "":
            errors.append("MODEL_FAST environment variable is required")
        if not self.model_reasoning or self.model_reasoning == "":
            errors.append("MODEL_REASONING environment variable is required")
        if not self.model_code or self.model_code == "":
            errors.append("MODEL_CODE environment variable is required")
        
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
