"""
core/orchestrator_async.py - Legacy Re-export
Point vers la nouvelle implémentation dans backend/domain/core/
"""

# Re-export complet depuis la source de vérité (backend/)
from backend.domain.core.orchestrator_async import (
    OrchestratorAsync,
    get_orchestrator,
    AgentState,
    analyzing_node,
    planning_node,
    coding_node,
    review_node,
    execute_node,
    should_fix_code,
)

# Pour compatibilité explicite avec l'ancien code
__all__ = [
    "OrchestratorAsync",
    "get_orchestrator",
    "AgentState",
]

# Alias pour les anciens imports directs
Orchestrator = OrchestratorAsync