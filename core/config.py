"""
Config loader - reads from config.yaml with environment variable overrides.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


# Default config path
CONFIG_PATH = Path("config.yaml")


@dataclass
class LLMConfig:
    """LLM configuration"""
    ollama_url: str = "http://localhost:11434"
    model_fast: str = "qwen2.5-coder:32b"
    model_reasoning: str = "qwen-opus"
    timeout: int = 30
    hf_token: Optional[str] = None


@dataclass
class ExecutorConfig:
    """Executor configuration"""
    timeout: int = 60
    workspace_dir: str = "workspace"
    cleanup: bool = True
    max_fix_attempts: int = 3
    blocked_patterns: list = field(default_factory=lambda: ["(eval(", "(exec(", "subprocess.Popen("])


@dataclass
class MemoryConfig:
    """Memory configuration"""
    enabled: bool = True
    model: str = "all-MiniLM-L6-v2"
    vector_dim: int = 384
    persist_path: str = "data/memory.index"
    top_k: int = 3


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    dir: str = "logs"
    max_size_mb: int = 10
    backup_count: int = 5
    format: str = "json"


@dataclass
class APIConfig:
    """API configuration"""
    host: str = "localhost"
    port: int = 8000
    api_key: str = ""
    enable_docs: bool = True


@dataclass
class DashboardConfig:
    """Dashboard configuration"""
    host: str = "0.0.0.0"
    port: int = 7860
    share: bool = False


@dataclass
class CodeReviewConfig:
    """Code review configuration"""
    enabled: bool = False
    tools: list = field(default_factory=lambda: ["bandit", "pylint"])
    fail_on: list = field(default_factory=lambda: ["high", "medium"])


@dataclass
class MetricsConfig:
    """Metrics configuration"""
    enabled: bool = True
    persist_path: str = "data/metrics.json"


@dataclass
class HealthConfig:
    """Health check configuration"""
    enabled: bool = True
    endpoint: str = "/health"


@dataclass
class WebSocketConfig:
    """WebSocket configuration"""
    enabled: bool = True
    ping_interval: int = 30


@dataclass
class Config:
    """Main configuration"""
    app_name: str = "UI-Pro"
    version: str = "1.0.0"
    debug: bool = False
    llm: LLMConfig = field(default_factory=LLMConfig)
    executor: ExecutorConfig = field(default_factory=ExecutorConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    api: APIConfig = field(default_factory=APIConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    code_review: CodeReviewConfig = field(default_factory=CodeReviewConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)


def _load_yaml(path: Path) -> dict:
    """Load YAML config file"""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Failed to load config from {path}: {e}")
        return {}


def _override_from_env(config: Config) -> None:
    """Override config from environment variables"""
    # LLM
    if env_ollama := os.getenv("OLLAMA_URL"):
        config.llm.ollama_url = env_ollama
    if env_model_fast := os.getenv("MODEL_FAST"):
        config.llm.model_fast = env_model_fast
    if env_model_reasoning := os.getenv("MODEL_REASONING"):
        config.llm.model_reasoning = env_model_reasoning
    if env_llm_timeout := os.getenv("LLM_TIMEOUT"):
        config.llm.timeout = int(env_llm_timeout)
    if env_hf_token := os.getenv("HF_TOKEN"):
        config.llm.hf_token = env_hf_token

    # Executor
    if env_exec_timeout := os.getenv("EXECUTOR_TIMEOUT"):
        config.executor.timeout = int(env_exec_timeout)

    # Logging
    if env_log_level := os.getenv("LOG_LEVEL"):
        config.logging.level = env_log_level

    # API
    if env_api_key := os.getenv("API_KEY"):
        config.api.api_key = env_api_key
    if env_api_port := os.getenv("API_PORT"):
        config.api.port = int(env_api_port)

    # Dashboard
    if env_dash_port := os.getenv("DASHBOARD_PORT"):
        config.dashboard.port = int(env_dash_port)


def load_config(path: Optional[Path] = None) -> Config:
    """
    Load configuration from YAML file with env var overrides.
    
    Priority: env vars > config.yaml > defaults
    """
    config_path = path or CONFIG_PATH
    
    # Load YAML
    yaml_config = _load_yaml(config_path)
    
    # Build config from YAML
    config = Config()
    
    if "app" in yaml_config:
        config.app_name = yaml_config["app"].get("name", config.app_name)
        config.version = yaml_config["app"].get("version", config.version)
        config.debug = yaml_config["app"].get("debug", config.debug)
    
    if "llm" in yaml_config:
        cfg = yaml_config["llm"]
        config.llm.ollama_url = cfg.get("ollama_url", config.llm.ollama_url)
        config.llm.model_fast = cfg.get("model_fast", config.llm.model_fast)
        config.llm.model_reasoning = cfg.get("model_reasoning", config.llm.model_reasoning)
        config.llm.timeout = cfg.get("timeout", config.llm.timeout)
    
    if "executor" in yaml_config:
        cfg = yaml_config["executor"]
        config.executor.timeout = cfg.get("timeout", config.executor.timeout)
        config.executor.workspace_dir = cfg.get("workspace_dir", config.executor.workspace_dir)
        config.executor.cleanup = cfg.get("cleanup", config.executor.cleanup)
        config.executor.max_fix_attempts = cfg.get("max_fix_attempts", config.executor.max_fix_attempts)
        if "blocked_patterns" in cfg:
            config.executor.blocked_patterns = cfg["blocked_patterns"]
    
    if "memory" in yaml_config:
        cfg = yaml_config["memory"]
        config.memory.enabled = cfg.get("enabled", config.memory.enabled)
        config.memory.model = cfg.get("model", config.memory.model)
        config.memory.vector_dim = cfg.get("vector_dim", config.memory.vector_dim)
        config.memory.persist_path = cfg.get("persist_path", config.memory.persist_path)
        config.memory.top_k = cfg.get("top_k", config.memory.top_k)
    
    if "logging" in yaml_config:
        cfg = yaml_config["logging"]
        config.logging.level = cfg.get("level", config.logging.level)
        config.logging.dir = cfg.get("dir", config.logging.dir)
        config.logging.max_size_mb = cfg.get("max_size_mb", config.logging.max_size_mb)
        config.logging.backup_count = cfg.get("backup_count", config.logging.backup_count)
        config.logging.format = cfg.get("format", config.logging.format)
    
    if "api" in yaml_config:
        cfg = yaml_config["api"]
        config.api.host = cfg.get("host", config.api.host)
        config.api.port = cfg.get("port", config.api.port)
        config.api.api_key = cfg.get("api_key", config.api.api_key)
        config.api.enable_docs = cfg.get("enable_docs", config.api.enable_docs)
    
    if "dashboard" in yaml_config:
        cfg = yaml_config["dashboard"]
        config.dashboard.host = cfg.get("host", config.dashboard.host)
        config.dashboard.port = cfg.get("port", config.dashboard.port)
        config.dashboard.share = cfg.get("share", config.dashboard.share)
    
    if "code_review" in yaml_config:
        cfg = yaml_config["code_review"]
        config.code_review.enabled = cfg.get("enabled", config.code_review.enabled)
        config.code_review.tools = cfg.get("tools", config.code_review.tools)
        config.code_review.fail_on = cfg.get("fail_on", config.code_review.fail_on)
    
    if "metrics" in yaml_config:
        cfg = yaml_config["metrics"]
        config.metrics.enabled = cfg.get("enabled", config.metrics.enabled)
        config.metrics.persist_path = cfg.get("persist_path", config.metrics.persist_path)
    
    if "health" in yaml_config:
        cfg = yaml_config["health"]
        config.health.enabled = cfg.get("enabled", config.health.enabled)
        config.health.endpoint = cfg.get("endpoint", config.health.endpoint)
    
    if "websocket" in yaml_config:
        cfg = yaml_config["websocket"]
        config.websocket.enabled = cfg.get("enabled", config.websocket.enabled)
        config.websocket.ping_interval = cfg.get("ping_interval", config.websocket.ping_interval)
    
    # Override from environment variables (highest priority)
    _override_from_env(config)
    
    return config


# Singleton instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get singleton config instance"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


# For convenience - expose common settings
config = get_config()