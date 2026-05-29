"""
backend/domain/settings.py - Configuration unifiée (Pydantic v2)
Single Source of Truth: YAML < ENV < Runtime Overrides
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ========================
# Model Presets
# ========================
class ModelPreset(BaseSettings):
    id: str
    name: str
    description: str
    model_fast: str
    model_reasoning: str
    model_code: str
    max_context: int = 8192
    recommended_for: list[str] = Field(default_factory=list)


DEFAULT_PRESETS: dict[str, ModelPreset] = {
    "light": ModelPreset(
        id="light",
        name="Light",
        description="Rapide et léger",
        model_fast="qwen3.5:0.8b",
        model_reasoning="qwen3.5:0.8b",
        model_code="qwen3.5:0.8b",
        max_context=4096,
        recommended_for=["quick", "simple"],
    ),
    "balanced": ModelPreset(
        id="balanced",
        name="Balanced",
        description="Bon équilibre",
        model_fast="qwen3.5:9b",
        model_reasoning="qwen3.5:9b",
        model_code="qwen3.5:9b",
        max_context=8192,
        recommended_for=["general", "coding"],
    ),
    "heavy": ModelPreset(
        id="heavy",
        name="Heavy",
        description="Maximum puissance",
        model_fast="qwen3.6:latest",
        model_reasoning="qwen3.6:latest",
        model_code="qwen3.6:latest",
        max_context=16384,
        recommended_for=["complex", "large_codebase"],
    ),
}


# ========================
# Settings Principal
# ========================
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # ========================
    # Paths (computed)
    # ========================
    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    workspace: str = "workspace"

    @property
    def workspace_path(self) -> Path:
        return PROJECT_ROOT / self.workspace

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def templates(self) -> Path:
        return PROJECT_ROOT / "templates"

    # ========================
    # Configuration
    # ========================
    app_name: str = "UI-Pro"
    version: str = "1.0.0"
    debug: bool = False

    ollama_url: str = "http://localhost:11434"
    lemonade_url: str = "http://localhost:13305"
    llamacpp_url: str = "http://localhost:8080"
    lmstudio_url: str = "http://localhost:1234"

    model_fast: str = ""
    model_reasoning: str = ""
    model_code: str = ""

    llm_timeout: int = Field(default=300, ge=10, le=1800)
    executor_timeout: int = Field(default=60, ge=5, le=600)

    log_level: str = Field(default="INFO")

    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_key: str | None = None

    dashboard_port: int = Field(default=7860, ge=1, le=65535)

    # CORS
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
        ],
        description="Allowed CORS origins for production",
    )

    memory_enabled: bool = True
    memory_limit_mb: int = Field(default=512, ge=100, le=4096)

    active_preset: str = Field(default="balanced", pattern="^(light|balanced|heavy)$")

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = Field(default=60, ge=1, le=10000)
    rate_limit_requests_per_hour: int = Field(default=1000, ge=10, le=100000)
    rate_limit_burst_size: int = Field(default=10, ge=1, le=100)

    # Memory persistence
    memory_persist_path: str = "data/memory.index"
    memory_docs_path: str = "data/memory_docs.pkl"

    # Checkpointing
    checkpoint_db_path: str = "data/checkpoints.db"
    checkpoint_max_per_thread: int = Field(default=100, ge=10, le=1000)
    checkpoint_prune_age_days: int = Field(default=30, ge=1, le=365)
    use_postgres_checkpointer: bool = False
    postgres_db_url: str | None = None

    # State management
    enable_state_compression: bool = True
    max_message_history: int = Field(default=50, ge=10, le=200)

    # Backends config
    backends_template: dict[str, dict[str, Any]] = Field(
        default={
            "ollama": {
                "url": "http://localhost:11434",
                "enabled": True,
                "models_endpoint": "/api/tags",
            },
            "lemonade": {
                "url": "http://localhost:13305",
                "enabled": True,
                "models_endpoint": "/api/v1/models",
            },
            "llamacpp": {
                "url": "http://localhost:8080",
                "enabled": False,
                "models_endpoint": "/props",
            },
            "lmstudio": {
                "url": "http://localhost:1234",
                "enabled": True,
                "models_endpoint": "/api/v1/models",
            },
        },
        exclude=True,
    )

    backends: dict[str, dict[str, Any]] = Field(default_factory=dict)

    # LangSmith Tracing
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "ui-pro"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # Deep copy default backends on each instance to avoid shared mutable state
        from copy import deepcopy

        self.backends = deepcopy(self.backends_template)

    # Runtime only (excluded from init)
    runtime_overrides: dict[str, Any] = Field(
        default_factory=dict, exclude=True, init=False
    )

    # ========================
    # Validators
    # ========================
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        return v.upper() if v.upper() in valid else "INFO"

    @model_validator(mode="after")
    def apply_preset_and_overrides(self) -> "Settings":
        """Applique le preset et les overrides runtime"""
        if self.active_preset in DEFAULT_PRESETS:
            preset = DEFAULT_PRESETS[self.active_preset]
            # Respecte les variables d'environnement (déjà chargées dans les champs)
            if not self.model_fast:
                self.model_fast = preset.model_fast
            if not self.model_reasoning:
                self.model_reasoning = preset.model_reasoning
            if not self.model_code:
                self.model_code = preset.model_code

        # Applique overrides runtime (UI)
        for k, v in self.runtime_overrides.items():
            if hasattr(self, k):
                setattr(self, k, v)

        return self

    # ========================
    # Méthodes métier
    # ========================
    def get_model_for_task(self, task: str) -> str:
        t = task.lower().strip()
        if t == "fast":
            return self.model_fast
        if t in ("reasoning", "reasoner"):
            return self.model_reasoning
        if t == "code":
            return self.model_code
        return self.model_fast or "qwen3.5:9b"

    def get_preset(self) -> ModelPreset:
        """Get the active model preset."""
        return DEFAULT_PRESETS.get(self.active_preset, DEFAULT_PRESETS["balanced"])

    def get_all_presets(self) -> dict[str, ModelPreset]:
        """Get all available presets."""
        return DEFAULT_PRESETS.copy()

    def auto_select_preset(self) -> str:
        """Auto-select the best preset based on available models and backends."""
        # Fallback: keep current preset (async model discovery removed preset logic)
        return self.active_preset

    def set_preset(self, preset_id: str) -> None:
        if preset_id not in DEFAULT_PRESETS:
            raise ValueError(f"Preset invalide: {preset_id}")
        self.active_preset = preset_id
        logger.info(f"Preset activé : {preset_id}")

    def set_timeout(self, llm: int, executor: int) -> None:
        self.llm_timeout = max(10, min(1800, llm))
        self.executor_timeout = max(5, min(600, executor))
        self._save_to_env(
            {
                "LLM_TIMEOUT": str(self.llm_timeout),
                "EXECUTOR_TIMEOUT": str(self.executor_timeout),
            }
        )

    def set_log_level(self, level: str) -> None:
        self.log_level = level.upper()
        self._save_to_env({"LOG_LEVEL": self.log_level})

    def set_runtime_override(self, key: str, value: Any) -> None:
        self.runtime_overrides[key] = value
        if hasattr(self, key):
            setattr(self, key, value)

    def clear_runtime_override(self, key: str) -> None:
        self.runtime_overrides.pop(key, None)

    def get_workspace_str(self) -> str:
        return str(self.workspace)

    def get_checkpoint_config(self) -> dict:
        return {
            "db_path": self.checkpoint_db_path,
            "max_per_thread": self.checkpoint_max_per_thread,
            "prune_age_days": self.checkpoint_prune_age_days,
            "use_postgres": self.use_postgres_checkpointer,
            "postgres_url": self.postgres_db_url,
        }

    def validate_settings(self) -> tuple[bool, list[str]]:
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

    def _save_to_env(self, updates: dict[str, str]) -> None:
        """Écriture atomique dans .env"""
        env_path = PROJECT_ROOT / ".env"
        try:
            lines = (
                env_path.read_text(encoding="utf-8").splitlines()
                if env_path.exists()
                else []
            )
            new_lines = []
            updated = set()

            for line in lines:
                if "=" in line:
                    key = line.split("=", 1)[0].strip()
                    if key in updates:
                        new_lines.append(f"{key}={updates[key]}")
                        updated.add(key)
                        continue
                new_lines.append(line)

            for key, val in updates.items():
                if key not in updated:
                    new_lines.append(f"{key}={val}")

            # Écriture atomique
            tmp = env_path.with_suffix(".tmp")
            tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            tmp.replace(env_path)
            logger.info(f"Updated .env: {list(updates.keys())}")

        except Exception as e:
            logger.error(f"Impossible de mettre à jour .env: {e}")


# ========================
# Singleton
# ========================
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
