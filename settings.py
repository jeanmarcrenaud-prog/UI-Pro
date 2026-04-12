"""
settings.py - Configuration centralisée pour UI-Pro
Source de vérité: lit config.yaml, puis override via .env
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import yaml

# Load .env file
LOAD_DOTENV = Path(".env").exists()
if LOAD_DOTENV:
    load_dotenv(".env")

PROJECT_ROOT = Path(__file__).parent
WORKSPACE = Path(os.getenv("WORKSPACE", "workspace"))
TEMPLATES = Path("templates")


def _load_yaml_config() -> Dict[str, Any]:
    """Load config from YAML file"""
    config_file = PROJECT_ROOT / "config.yaml"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load config.yaml: {e}")
            return {}
    return {}


class Settings:
    """Configuration centralisée - lit config.yaml + override .env"""
    
    def __init__(self):
        # Load base config from YAML
        config = _load_yaml_config()
        app_config = config.get("app", {})
        llm_config = config.get("llm", {})
        executor_config = config.get("executor", {})
        memory_config = config.get("memory", {})
        logging_config = config.get("logging", {})
        api_config = config.get("api", {})
        dashboard_config = config.get("dashboard", {})
        
        # App
        self.app_name = app_config.get("name", "UI-Pro")
        self.version = app_config.get("version", "1.0.0")
        self.debug = app_config.get("debug", False)
        
        # LLM - env override yaml
        self.ollama_url = os.getenv("OLLAMA_URL", llm_config.get("ollama_url", "http://localhost:11434"))
        self.model_fast = os.getenv("MODEL_FAST", llm_config.get("model_fast", "qwen3.5:9b"))
        self.model_reasoning = os.getenv("MODEL_REASONING", llm_config.get("model_reasoning", "qwen3.5:9b"))
        self.llm_timeout = int(os.getenv("LLM_TIMEOUT", llm_config.get("timeout", 30)))
        
        # Executor - env override yaml
        self.executor_timeout = int(os.getenv("EXECUTOR_TIMEOUT", executor_config.get("timeout", 60)))
        self.executor_workspace = executor_config.get("workspace_dir", "workspace")
        self.executor_cleanup = executor_config.get("cleanup", True)
        self.executor_max_fix = executor_config.get("max_fix_attempts", 3)
        self.memory_limit_mb = int(os.getenv("MEMORY_LIMIT_MB", 512))
        
        # Memory - env override yaml
        self.memory_enabled = memory_config.get("enabled", True)
        self.memory_model = memory_config.get("model", "all-MiniLM-L6-v2")
        self.memory_vector_dim = memory_config.get("vector_dim", 384)
        
        # Logging - env override yaml
        self.log_level = os.getenv("LOG_LEVEL", logging_config.get("level", "INFO"))
        self.log_dir = logging_config.get("dir", "logs")
        
        # API - env override yaml
        self.api_host = os.getenv("API_HOST", api_config.get("host", "localhost"))
        self.api_port = int(os.getenv("API_PORT", api_config.get("port", 8000)))
        self.api_key = os.getenv("API_KEY", api_config.get("api_key", ""))
        
        # Dashboard - env override yaml
        self.dashboard_port = int(os.getenv("DASHBOARD_PORT", dashboard_config.get("port", 7860)))
        
        # Workspace path
        self.workspace = str(WORKSPACE)
        self.load_dotenv = LOAD_DOTENV
    
    def get_model_for_task(self, task_type: str) -> str:
        """Smart model selection based on task type."""
        reasoning_keywords = [
            "error", "debug", "optimize", "architecture",
            "complex", "plan", "architect", "reason",
        ]
        task_lower = task_type.lower()
        
        if task_lower == "fast":
            return self.model_fast
        if task_lower == "reasoning":
            return self.model_reasoning
        if any(keyword in task_lower for keyword in reasoning_keywords):
            return self.model_reasoning
        return self.model_fast


# Singleton with explicit typing
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


settings = get_settings()


def get_model_for_task(task_type: str) -> str:
    """Smart model selection based on task type."""
    return settings.get_model_for_task(task_type)
