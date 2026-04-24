# models/__init__.py - Modèles de données et schemas pour UI-Pro
"""
Models - Data schemas and business structures.

Ce dossier contient les types Pydantic/dataclass qui décrivent les structures
de données de l'application (et NON la logique).

 POUR LA LOGIQUE, utiliser :
- core/memory.py    : FAISS memory integration
- core/state_manager.py : State management  
- core/config.py    : Configuration
- core/executor.py : Code execution
- llm/router.py   : LLM routing
- services/*     : Services

 Exports:
- Configuration: Settings, settings (NOTE: import depuis .settings)
- Metrics: Metrics, MetricsManager (NOTE: import depuis .metrics)
- LLM: LLMRouter, ModelsConfig (NOTE: import depuis llm.router)
"""

from core.config import Config, get_config
from core.metrics import Metrics, MetricsManager
from .settings import Settings, settings

# MemoryManager EST dans core/memory.py (logique), PAS ici
# State et StateManager sont dans core/state_manager.py
# LLMRouter et ModelsConfig sont dans llm.router

__all__ = [ 
    "Config",
    "get_config",
    "Metrics",
    "MetricsManager",
    "Settings",
    "settings",
]