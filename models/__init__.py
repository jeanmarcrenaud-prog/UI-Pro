# models/__init__.py - Modèles de données et schemas pour UI-Pro
"""
Models - Data schemas and business structures.

Ce dossier contient les types Pydantic/dataclass qui décrivent les structures
de données de l'application (et NON la logique).

 POUR LA LOGIQUE, utiliser :
- core/memory.py    : FAISS memory integration
- core/state_manager.py : State management  
- llm/router.py   : LLM routing
- services/*     : Services

 Exports:
- Configuration: Settings, settings
- State: State, StateManager, AgentState, RunStatus
- Metrics: Metrics, MetricsManager
- Memory: MemoryItem (NOTE: MemoryManager est dans core/memory.py)
- LLM: LLMRouter, ModelsConfig
"""

from .state import State, StateManager
from .config import Config, get_config
from .metrics import Metrics, MetricsManager
from .settings import Settings, settings

# MemoryManager EST dans core/memory.py (logique), PAS ici
# Si vous avez besoin de MemoryManager, importez desde core.memory

# State exports
__all__ = [
    "State",
    "StateManager", 
    "Config",
    "get_config",
    "Metrics",
    "MetricsManager",
    "Settings",
    "settings",
]