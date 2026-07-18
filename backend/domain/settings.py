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


# DEFAULT_PRESETS is a minimal fallback when model discovery is unavailable.
# The actual presets are generated dynamically by ModelDiscovery.
DEFAULT_PRESETS: dict[str, ModelPreset] = {
    "default": ModelPreset(
        id="default",
        name="Default",
        description="Fallback preset",
        model_fast="",
        model_reasoning="",
        model_code="",
        max_context=4096,
        recommended_for=["general"],
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
    opendesign_url: str = "http://localhost:7456"

    # Health check tuning for the /health/deep endpoint. The fast /health
    # probe intentionally does no I/O so Docker/k8s load balancers can
    # check it in <50ms; only /health/deep hits these. health_timeout is
    # the per-backend probe deadline (lower than llm_timeout because we
    # only need a /api/version or /api/ps round-trip). required_models
    # lets production deployments assert that the expected model set is
    # installed — if any are missing, /health/deep returns "degraded"
    # rather than "healthy", so an alert can fire BEFORE the user
    # notices the model is gone.
    ollama_health_timeout: int = Field(default=5, ge=1, le=30)
    ollama_required_models: list[str] = Field(default_factory=list)

    model_fast: str = ""
    model_reasoning: str = ""
    model_code: str = ""

    # Default bumped 600s -> 900s to accommodate reasoning models
    # (qwen3.5:9b / qwen3.6:latest) on long prompts. See README
    # "Troubleshooting > LLM_TIMEOUT" for the full rationale and the
    # relationship with the per-backend `read_timeout` below.
    # Floor raised 10s -> 30s: even the "fast" tier can stall for 10-20s on
    # the first request after VRAM load (Ollama model compile + load). A
    # 10s floor is silently misconfigurable via the Settings UI slider,
    # which previously caused repeated "LLM call timed out after 10.0s"
    # failures on small models. See the live-test note in commit history
    # for the reasoning-model timing.
    llm_timeout: int = Field(default=900, ge=30, le=1800)
    executor_timeout: int = Field(default=60, ge=5, le=600)

    # When True, the coding_node retry path uses the advanced self-correction
    # prompt (chain-of-thought + self-critique blocks before the code). When
    # False (default), it uses the basic fix prompt — context-only, no
    # explicit CoT. The advanced prompt costs ~30% of the token budget on
    # the meta-cognition blocks, which 9B-class models spend at the
    # expense of the final code (often truncating it). 14B+ models benefit
    # from it. Default OFF keeps the 9B default-model path safe.
    advanced_self_critique: bool = False

    # Qwen3.5+ and other "thinking-mode" models (Qwen, DeepSeek-R1, OpenAI o1/o3)
    # spend the majority of their `max_tokens` budget on internal chain-of-thought
    # BEFORE any visible output. Live test on qwen3.5-9b (9B parameters) with
    # max_tokens=8000: 7999 tokens of reasoning, 0 of visible code. With
    # enable_thinking=False: 4199 of 4706 are still reasoning, but the remaining
    # 507 tokens produce the actual code response. Non-thinking models (lfm2.5,
    # llama-3, mistral) ignore this parameter. Default is OFF because the
    # default user-facing experience is "give me code" not "show me your
    # thinking". Set to True for o1/o3-style models where reasoning IS the answer.
    llm_enable_thinking: bool = False

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

    active_preset: str = Field(default="balanced")

    # Per-node model routing: when True (default), each pipeline node
    # (analyzing/plan/code/review) uses the preset tier (fast/reasoning)
    # instead of the user-selected chat model. When False, every node
    # uses the user model (legacy behavior). Toggle is session-only —
    # the change applies immediately, no restart required.
    node_routing_enabled: bool = False

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

    # Approval timeout
    approval_timeout_minutes: int = Field(default=10, ge=1, le=60,
        description="Max minutes to wait for human approval before auto-cancelling")
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
                # Per-backend read_timeout. MUST stay <= llm_timeout or
                # the backend will kill the stream before the outer LLM
                # deadline fires. Default raised 300s -> 900s to match
                # the new llm_timeout default above.
                "timeout": 900,
            },
            "lemonade": {
                "url": "http://localhost:13305",
                "enabled": True,
                "models_endpoint": "/api/v1/models",
                "timeout": 900,
            },
            "llamacpp": {
                "url": "http://localhost:8080",
                "enabled": False,
                "models_endpoint": "/props",
                "timeout": 900,
            },
            "lmstudio": {
                "url": "http://localhost:1234",
                "enabled": True,
                "models_endpoint": "/api/v1/models",
                "timeout": 900,
            },
            "opendesign": {
                "url": "http://localhost:7456",
                "enabled": True,
                "models_endpoint": "/api/agents",
                "timeout": 900,
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
        # Sync per-backend timeouts with llm_timeout so the HTTP client
        # doesn't kill the stream before the outer LLM deadline fires.
        for cfg in self.backends.values():
            cfg["timeout"] = self.llm_timeout

        if self.llm_timeout < 120:
            logger.warning(
                f"llm_timeout={self.llm_timeout}s is too short for larger models, "
                f"recommended >= 120s. Adjust .env or use Settings UI."
            )

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
        """Applique les overrides runtime"""
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
        return self.model_fast or ""

    def get_preset(self) -> ModelPreset | None:
        """Get the active model preset (fallback)."""
        return DEFAULT_PRESETS.get(self.active_preset)

    def get_all_presets(self) -> dict[str, ModelPreset]:
        """Get all available presets (fallback)."""
        return DEFAULT_PRESETS.copy()

    def auto_select_preset(self) -> str:
        """Auto-select the best preset based on available models.
        Uses ModelDiscovery to find the most capable model and
        returns the preset name that uses it.
        """
        try:
            from backend.infrastructure.model_discovery import (
                get_model_discovery, generate_dynamic_presets,
            )
            import asyncio
            discovery = get_model_discovery()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                models = loop.run_until_complete(discovery.discover_all())
                presets = generate_dynamic_presets(models)
                # Prefer heavy if available, then balanced, then fast
                for preferred in ("heavy", "balanced", "fast"):
                    if preferred in presets:
                        return preferred
            finally:
                loop.close()
        except Exception as e:
            logger.debug("auto_select_preset discovery failed: %s", e)
        return self.active_preset

    def set_preset(self, preset_id: str) -> None:
        self.active_preset = preset_id
        logger.info(f"Preset activé : {preset_id}")

    def set_timeout(self, llm: int, executor: int) -> None:
        # Floor matches the Pydantic Field constraint (ge=30). The clamp
        # is redundant for env-var-driven loads (those go through Settings
        # validation) but is the only defense for runtime overrides via
        # the Settings UI — keeping them aligned prevents the slider from
        # writing a value the next Settings() reload would reject.
        self.llm_timeout = max(30, min(1800, llm))
        self.executor_timeout = max(5, min(600, executor))
        # Sync per-backend timeouts so the HTTP client doesn't
        # kill the stream before the outer LLM deadline fires.
        for cfg in self.backends.values():
            cfg["timeout"] = self.llm_timeout
        self._save_to_env(
            {
                "LLM_TIMEOUT": str(self.llm_timeout),
                "EXECUTOR_TIMEOUT": str(self.executor_timeout),
            }
        )

    def reload_from_env(self) -> None:
        """Re-read .env and update this instance in place.

        The Settings class is normally instantiated exactly once at
        process start, via the @lru_cache(maxsize=1) on get_settings().
        Every consumer holds a direct reference to that single instance
        (e.g. `from backend.domain.settings import settings`), so
        re-assigning the module attribute would not update them. The
        fix is to mutate the existing instance in place.

        Behavior:
          1. Clear the lru_cache so get_settings() will re-construct.
          2. Build a fresh Settings() with the current .env / env vars.
             If the new env is invalid (e.g. LLM_TIMEOUT=10 below the
             ge=30 floor), the pydantic ValidationError propagates and
             this instance is left UNTOUCHED. The cache stays cleared
             so the next call retries with the same bad config.
          3. Snapshot runtime_overrides — these are Field(exclude=True,
             init=False) in-memory state (UI toggles like
             node_routing_enabled, llm_enable_thinking) that must NOT
             be reset by a .env reload, because the user may have
             toggled them after process start.
          4. Copy every declared model field from the fresh instance
             onto this one.
          5. Restore runtime_overrides (defense in depth: the setattr
             loop already skips it via the `if field_name == ...`
             guard, but we restore explicitly to make the intent
             unambiguous to readers).

        Use case: change LLM_TIMEOUT in .env, then call this from
        /api/settings/reload. The running server picks up the new
        value without a process restart, and any in-progress pipeline
        run sees the new timeout on its next LLM call.
        """
        get_settings.cache_clear()
        fresh = get_settings()  # raises ValidationError on bad env

        saved_overrides = self.runtime_overrides.copy()

        for field_name in type(self).model_fields:
            if field_name == "runtime_overrides":
                continue
            setattr(self, field_name, getattr(fresh, field_name))

        self.runtime_overrides = saved_overrides
        logger.info(
            "Settings reloaded from env (llm_timeout=%ss, executor_timeout=%ss)",
            self.llm_timeout,
            self.executor_timeout,
        )

    def set_log_level(self, level: str) -> None:
        self.log_level = level.upper()
        self._save_to_env({"LOG_LEVEL": self.log_level})

    def set_runtime_override(self, key: str, value: Any) -> None:
        self.runtime_overrides[key] = value
        if hasattr(self, key):
            setattr(self, key, value)

    def get_node_routing_enabled(self) -> bool:
        """Whether each pipeline node routes to its preset tier.

        Read from runtime_overrides first (UI toggle), falling back
        to the constructor default (env or True).
        """
        return bool(self.runtime_overrides.get("node_routing_enabled", self.node_routing_enabled))

    def set_node_routing(self, enabled: bool) -> None:
        """Toggle per-node routing. No-op for LLM router singletons —
        nodes.py reads this on every call, so the change applies to
        the next pipeline run without a restart.
        """
        self.set_runtime_override("node_routing_enabled", bool(enabled))
        self._invalidate_provider_singletons()

    def get_llm_enable_thinking(self) -> bool:
        """Whether to let thinking-mode models (Qwen3.5+, o1, DeepSeek-R1)
        spend tokens on internal chain-of-thought before responding.

        Read from runtime_overrides first (API toggle), falling back to
        the constructor default (env or False).
        """
        return bool(self.runtime_overrides.get("llm_enable_thinking", self.llm_enable_thinking))

    def set_llm_enable_thinking(self, enabled: bool) -> None:
        """Toggle thinking mode at runtime. Sent as `chat_template_kwargs`
        to all OpenAI-compatible backends. Non-thinking models ignore it.
        """
        self.set_runtime_override("llm_enable_thinking", bool(enabled))
        # No need to invalidate singletons — the mixin reads this fresh
        # on every request.

    def _invalidate_provider_singletons(self) -> None:
        """Reset cached router so runtime changes (model, URL, provider) take effect."""
        try:
            import backend.domain.core.langgraph.nodes as _nodes

            _nodes._llm_router_instance = None
        except Exception:
            pass

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
