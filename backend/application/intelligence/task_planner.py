import logging
from typing import List, Dict, Any, Optional
from backend.domain.core.models import Action, EditorState, DelegateAction
from backend.domain.core.action_executor import ActionExecutor

logger = logging.getLogger(__name__)

class TaskPlanner:
    """
    Responsable de la décomposition des intentions utilisateurs en plans d'actions.
    Il décide si une tâche doit être exécutée par Hermes (atomique) 
    ou déléguée à OpenCode (complexe).
    """
    def __init__(self, model_provider: Any = None):
        # Le model_provider peut être injecté pour appeler le LLM (ex: Ollama, LM Studio)
        self.model_provider = model_provider

    def generate_plan(self, intent: str, state: EditorState) -> List[Action]:
        """
        Analyse l'intention et retourne une liste d'actions.
        Si la tâche est complexe, retourne une action de type 'opencode_delegate'.
        """
        logger.info(f"Planification de l'intention : {intent}")

        # Simulation de la logique de décision du LLM
        # En production, cette section sera remplacée par un appel LLM avec le prompt ci-dessous.
        
        complex_keywords = [
            "crée une application", "implémente un système", "développe un projet", 
            "génère une API", "refactorise tout le dossier", "écris un framework"
        ]

        if any(keyword in intent.lower() for keyword in complex_keywords):
            logger.info("Intention complexe détectée -> Délégation à OpenCode.")
            return [
                Action(
                    action_type="opencode_delegate",
                    params={"task": intent},
                    status="delegated"
                )
            ]
        
        # Logique par défaut : Décomposer en actions atomiques simples
        # Cette partie sera enrichie par les prompts du LLM pour une décomposition réelle
        logger.info("Intention atomique détectée -> Décomposition interne.")
        
        # Exemple de décomposition simple (à remplacer par l'appel LLM)
        if "ouvrir" in intent.lower():
            # Extraire le chemin (simplifié)
            path = "path/to/file.py" 
            return [
                Action(action_type="open_file", params={"path": path}, status="pending")
            ]
        
        # Si on ne sait pas quoi faire, on demande au LLM de créer un plan atomique
        # Pour l'instant, on retourne une action de test
        return [
            Action(action_type="insert_code", params={"content": "print('Action placeholder')"}, status="pending")
        ]

# Singleton
_task_planner: Optional[TaskPlanner] = None

def get_task_planner() -> TaskPlanner:
    global _task_planner
    if _task_planner is None:
        _task_planner = TaskPlanner()
    return _task_planner
