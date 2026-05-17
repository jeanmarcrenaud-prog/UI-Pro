# models/__init__.py - Modèles de données et schemas pour UI-Pro
"""
Models - Data schemas and business structures.

Ce dossier contient les types Pydantic/dataclass qui décrivent les structures
de données de l'application (et NON la logique).

 POUR LA LOGIQUE, utiliser backend/ :
  - backend/domain/core/ : Core business logic
  - backend/infrastructure/ : Services and infrastructure
  - backend/transport/ : API and transport

  Exports:
 - Configuration: Settings, settings (NOTE: import depuis .settings)
 - Metrics: Metrics, MetricsManager (NOTE: import depuis backend.domain.core.metrics)
"""
from backend.domain.core.metrics import Metrics, MetricsManager
from .settings import Settings, settings

__all__ = [ 
    "Metrics",
    "MetricsManager",
    "Settings",
    "settings",
]