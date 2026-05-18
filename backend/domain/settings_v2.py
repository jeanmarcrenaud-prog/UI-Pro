"""
backend/domain/settings_v2.py - Unified Configuration with pydantic-settings

Role: Single source of truth for all settings using pydantic-settings.
Priority: YAML config < Environment variables < Runtime overrides (UI)

Features:
- Automatic YAML + env var loading via pydantic-settings
- Type validation and conversion
- Runtime override support (for UI controls)
- Singleton pattern for performance
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Project root path
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ========================
# YAML Config Loader
# ========================
def _load_yaml_config() -> Dict[str, Any]:
    """Load config from YAML file."""
    config_file = PROJECT_ROOT / "config.yaml"
    if config_file.exists():
        try:
            import yaml
            with open(config_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load config.yaml: {e}")
    return {}


YAML_CONFIG = _load_yaml_config()


# ========================
# Model Presets Configuration
# ========================
class ModelPreset(BaseSettings):
    """Model preset definition - can be loaded from YAML or env."""
    
    # Preset identifiers
    id: str = ""  # "light", "balanced", "heavy"
    name: str = ""
    description: str = ""
    
    # Model selection for this preset
    model_fast: str = ""
    model_reasoning: str = ""
    model_code: str = ""
    
    # Performance characteristics
    max_context: int = 8192
    recommended_for: List[str] = Field(default_factory=list)
    
    @field_validator("recommended_for", mode="before")
    @classmethod
    def parse_recommended_for(cls, v):
        if isinstance(v, str):
            return [v]
        return v or []


# Default presets
DEFAULT_PRESETS: Dict[str, ModelPreset] = {
    "light": ModelPreset(
        id="light",
        name="Light",
        description="Fast responses, lower resource usage",
        model_fast="qwen3.5:0.8b",
        model_reasoning="qwen3.5:0.8b",
        model_code="qwen3.5:0.8b",
        max_context=4096,
        recommended_for=["quick_questions", "simple_code", "summaries"],
    ),
    "balanced": ModelPreset(
        id="balanced",
        name="Balanced",
        description="Good balance of speed and capability",
        model_fast="qwen3.5:9b",
        model_reasoning="qwen3.5:9b",
        model_code="qwen3.5:9b",
        max_context=8192,
        recommended_for=["general_tasks", "coding", "reasoning"],
    ),
    "heavy": ModelPreset(
        id="heavy",
        name="Heavy",
        description="Maximum capability, higher resource usage",
        model_fast="qwen3.6:latest",
        model_reasoning="qwen3.6:latest",
        model_code="qwen3.6:latest",
        max_context=16384,
        recommended_for=["complex_reasoning", "large_codebases", "deep_analysis"],
    ),
}


# ========================
# Main Settings Class
# ========================
class Settings(BaseSettings):
    """
    Unified settings using pydantic-settings.
    
    Priority (lowest to highest):
    1. YAML config.yaml
    2. Environment variables
    3. Runtime overrides (set via code)
    
    Environment variables take precedence over YAML.
    Runtime overrides take precedence over everything.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields
    )
    
    # ========================
    # Paths (computed, not from env)
    # ========================
    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT
    
    @property
    def workspace(self) -> Path:
        return PROJECT_ROOT / os.getenv("WORKSPACE", "workspace")
    
    @property
    def templates(self) -> Path:
        return PROJECT_ROOT / "templates"
    
    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"
    
    # ========================
    # LLM Backend URLs
    # ========================
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL"
    )
    lemonade_url: str = Field(
        default="http://localhost:13305",
        description="Lemonade server URL"
    )
    llamacpp_url: str = Field(
        default="http://localhost:8080",
        description="llama.cpp server URL"
    )
    lmstudio_url: str = Field(
        default="http://localhost:1234",
        description="LM Studio server URL"
    )
    
    # ========================
    # Model Configuration
    # ========================
    model_fast: str = Field(
        default="",
        description="Fast model for simple tasks"
    )
    model_reasoning: str = Field(
        default="",
        description="Reasoning model for complex tasks"
    )
    model_code: str = Field(
        default="",
        description="Code-specific model"
    )
    
    # ========================
    # Timeouts
    # ========================
    llm_timeout: int = Field(
        default=300,
        ge=10,
        le=1800,
        description="LLM API timeout in seconds"
    )
    executor_timeout: int = Field(
        default=60,
        ge=5,
        le=600,
        description="Code execution timeout in seconds"
    )
    
    # ========================
    # Logging
    # ========================
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        return v.upper() if v.upper() in valid_levels else "INFO"
    
    # ========================
    # Application Settings (from YAML with env override)
    # ========================
    app_name: str = Field(
        default="UI-Pro",
        description="Application name"
    )
    version: str = Field(
        default="1.0.0",
        description="Application version"
    )
    debug: bool = Field(
        default=False,
        description="Debug mode"
    )
    
    # ========================
    # API Settings
    # ========================
    api_host: str = Field(
        default="localhost",
        description="API host"
    )
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API port"
    )
    api_key: str = Field(
        default="",
        description="API key (from env only for security)"
    )
    
    # ========================
    # Dashboard Settings
    # ========================
    dashboard_port: int = Field(
        default=7860,
        ge=1,
        le=65535,
        description="Dashboard port"
    )
    
    # ========================
    # Memory Settings
    # ========================
    memory_enabled: bool = Field(
        default=True,
        description="Enable vector memory"
    )
    memory_limit_mb: int = Field(
        default=512,
        ge=100,
        le=4096,
        description="Memory limit in MB"
    )
    
    # ========================
    # Checkpointing Settings
    # ========================
    checkpoint_db_path: str = Field(
        default="data/checkpoints.db",
        description="SQLite checkpoint database path"
    )
    checkpoint_max_per_thread: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Max checkpoints per thread"
    )
    checkpoint_prune_age_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Checkpoint pruning age in days"
    )
    use_postgres_checkpointer: bool = Field(
        default=False,
        description="Use PostgreSQL for checkpointing"
    )
    postgres_db_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection URL"
    )
    
    # ========================
    # State Management
    # ========================
    enable_state_compression: bool = Field(
        default=True,
        description="Enable state compression"
    )
    max_message_history: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Max message history before summarization"
    )
    
    # ========================
    # Backend Configuration
    # ========================
    backends: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "ollama": {"url": "http://localhost:11434", "enabled": True, "models_endpoint": "/api/tags"},
            "lemonade": {"url": "http://localhost:13305", "enabled": True, "models_endpoint": "/api/v1/models"},
            "llamacpp": {"url": "http://localhost:8080", "enabled": False, "models_endpoint": "/props"},
            "lmstudio": {"url": "http://localhost:1234", "enabled": True, "models_endpoint": "/api/v1/models"},
        },
        description="Backend configuration"
    )
    
    # ========================
    # Active Preset
    # ========================
    active_preset: str = Field(
        default="balanced",
        description="Active model preset (light/balanced/heavy)"
    )
    
    @field_validator("active_preset")
    @classmethod
    def validate_preset(cls, v: str) -> str:
        valid_presets = {"light", "balanced", "heavy"}
        return v if v in valid_presets else "balanced"
    
    # ========================
    # Runtime Overrides Storage
    # ========================
    _runtime_overrides: Dict[str, Any] = {}
    
    def __init__(self, **data):
        # Apply YAML config first
        yaml_data = self._get_yaml_overrides()
        # Merge with provided data (env vars will override)
        merged = {**yaml_data, **data}
        super().__init__(**merged)
        
        # Apply runtime overrides if any
        for key, value in self._runtime_overrides.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def _get_yaml_overrides(self) -> Dict[str, Any]:
        """Extract overrides from YAML config."""
        overrides = {}
        
        # App settings
        if "app" in YAML_CONFIG:
            app = YAML_CONFIG["app"]
            if "name" in app:
                overrides["app_name"] = app["name"]
            if "version" in app:
                overrides["version"] = app["version"]
            if "debug" in app:
                overrides["debug"] = app["debug"]
        
        # API settings
        if "api" in YAML_CONFIG:
            api = YAML_CONFIG["api"]
            if "host" in api:
                overrides["api_host"] = api["host"]
            if "port" in api:
                overrides["api_port"] = api["port"]
            if "dashboard_port" in api:
                overrides["dashboard_port"] = api["dashboard_port"]
        
        # Memory settings
        if "memory" in YAML_CONFIG:
            memory = YAML_CONFIG["memory"]
            if "enabled" in memory:
                overrides["memory_enabled"] = memory["enabled"]
            if "limit_mb" in memory:
                overrides["memory_limit_mb"] = memory["limit_mb"]
        
        return overrides
    
    # ========================
    # Methods
    # ========================
    def get_model_for_task(self, task: str) -> str:
        """
        Get model for task type.
        
        Args:
            task: Task type ("fast", "reasoning", "code")
        
        Returns:
            Model name for the task
        """
        task_lower = task.lower().strip()
        
        if task_lower == "fast":
            return self.model_fast
        if task_lower in ("reasoning", "reasoner"):
            return self.model_reasoning
        if task_lower == "code":
            return self.model_code
        
        return self.model_fast
    
    def get_preset(self) -> ModelPreset:
        """Get the active model preset."""
        return DEFAULT_PRESETS.get(self.active_preset, DEFAULT_PRESETS["balanced"])
    
    def set_preset(self, preset_id: str) -> None:
        """Set active preset and update models accordingly."""
        if preset_id not in DEFAULT_PRESETS:
            raise ValueError(f"Invalid preset: {preset_id}. Must be one of: {list(DEFAULT_PRESETS.keys())}")
        
        preset = DEFAULT_PRESETS[preset_id]
        self.active_preset = preset_id
        
        # Update models from preset (if not overridden by env)
        if not os.getenv("MODEL_FAST"):
            self.model_fast = preset.model_fast
        if not os.getenv("MODEL_REASONING"):
            self.model_reasoning = preset.model_reasoning
        if not os.getenv("MODEL_CODE"):
            self.model_code = preset.model_code
        
        logger.info(f"Switched to preset: {preset_id}")
    
    def get_all_presets(self) -> Dict[str, ModelPreset]:
        """Get all available presets."""
        return DEFAULT_PRESETS.copy()
    
    def get_workspace_str(self) -> str:
        """Get workspace as string."""
        return str(self.workspace)
    
    def set_timeout(self, llm_timeout: int, executor_timeout: int) -> None:
        """Set timeouts with validation."""
        self.llm_timeout = max(10, min(1800, llm_timeout))
        self.executor_timeout = max(5, min(600, executor_timeout))
        self._persist_to_env("LLM_TIMEOUT", str(self.llm_timeout))
        self._persist_to_env("EXECUTOR_TIMEOUT", str(self.executor_timeout))
        logger.info(f"Updated timeouts: LLM={self.llm_timeout}s, EXECUTOR={self.executor_timeout}s")
    
    def set_log_level(self, level: str) -> None:
        """Set log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        level_upper = level.upper()
        if level_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {level}")
        self.log_level = level_upper
        self._persist_to_env("LOG_LEVEL", level_upper)
        logger.info(f"Log level set to: {level_upper}")
    
    def set_runtime_override(self, key: str, value: Any) -> None:
        """Set runtime override (for UI controls)."""
        self._runtime_overrides[key] = value
        if hasattr(self, key):
            setattr(self, key, value)
        logger.debug(f"Runtime override set: {key}={value}")
    
    def clear_runtime_override(self, key: str) -> None:
        """Clear a runtime override."""
        self._runtime_overrides.pop(key, None)
    
    def _persist_to_env(self, key: str, value: str) -> None:
        """Persist setting to .env file."""
        env_file = PROJECT_ROOT / ".env"
        try:
            lines = []
            if env_file.exists():
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            
            found = False
            new_lines = []
            for line in lines:
                if line.strip().startswith(f"{key}="):
                    new_lines.append(f"{key}={value}\n")
                    found = True
                else:
                    new_lines.append(line)
            
            if not found:
                new_lines.append(f"{key}={value}\n")
            
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception as e:
            logger.warning(f"Could not persist {key} to .env: {e}")
    
    def validate(self) -> tuple[bool, List[str]]:
        """Validate configuration."""
        errors = []
        
        if self.api_port <= 0 or self.api_port > 65535:
            errors.append(f"Invalid api_port: {self.api_port}")
        
        if self.dashboard_port <= 0 or self.dashboard_port > 65535:
            errors.append(f"Invalid dashboard_port: {self.dashboard_port}")
        
        if not self.model_fast:
            errors.append("MODEL_FAST is required (set via env or preset)")
        if not self.model_reasoning:
            errors.append("MODEL_REASONING is required (set via env or preset)")
        if not self.model_code:
            errors.append("MODEL_CODE is required (set via env or preset)")
        
        if not self.workspace.exists():
            try:
                self.workspace.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create workspace: {e}")
        
        return len(errors) == 0, errors


# ========================
# Singleton
# =====================@
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Convenience singleton
settings = get_settings()