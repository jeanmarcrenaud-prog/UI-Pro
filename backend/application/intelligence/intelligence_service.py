import asyncio
import logging
from typing import List, Dict, Any, Optional
from backend.domain.core.models import Action, EditorState, HermesAction, DelegateAction
from backend.domain.core.action_executor import ActionExecutor
from backend.infrastructure.opencode_connector.manager import OpenCodeConnectorManager

logger = logging.getLogger(__name__)

class IntelligenceService:
    """
    Service de haut niveau responsable de la compréhension des intentions utilisateurs
    et de la planification des actions nécessaires.
    """
    def __init__(
        self, 
        planner: Any, 
        executor: ActionExecutor,
        connector_manager: OpenCodeConnectorManager
    ):
        self.planner = planner
        self.executor = executor
        self.connector_manager = connector_manager
        self.project_path = "workspace"  # configurable via settings

    async def process_user_intent(self, intent_description: str, current_state: EditorState) -> List[Action]:
        """Analyze intent -> planner decides (delegate vs local actions)."""
        logger.info(f"Processing intent: {intent_description}")

        plan = self.planner.generate_plan(intent_description, current_state)

        actions = []
        for step in plan:
            if isinstance(step, DelegateAction):
                logger.info(f"Delegating to OpenCode: {step.task}")
                delegated = await self.delegate_to_opencode(step.task, current_state)
                actions.extend(delegated)
            elif isinstance(step, HermesAction):
                action_result = self.executor.execute_action(step.action_type, step.params)
                if action_result.get("status") == "success":
                    actions.append(Action(
                        action_type=step.action_type,
                        params=step.params,
                        status="success"
                    ))
                else:
                    logger.error(f"Failed: {step.action_type}: {action_result.get('message')}")
            else:
                logger.warning(f"Unknown action type: {type(step).__name__}")

        return actions

    async def delegate_to_opencode(self, task: str, current_state: EditorState) -> List[Action]:
        """
        Déléguer une tâche à OpenCode via le connector manager.
        Retourne une Action contenant la réponse de l'agent.
        """
        logger.info(f"Delegating to OpenCode: {task}")
        # Correction: utiliser send_task au lieu de run
        success = await self.connector_manager.send_task(task)

        return [Action(
            action_type="opencode_delegate",
            status="success" if success else "failed",
            params={
                "task": task,
                "project": self.project_path,
                "response": "Task submitted successfully" if success else "Failed to submit",
                "session_id": "current_session" # À remplacer par le vrai ID si disponible
            },
        )]

    async def get_opencode_status(self) -> str:
        """
        Récupère un résumé des dernières actions d'OpenCode pour que l'agent
        puisse savoir ce qui se passe en arrière-plan.
        """
        notifications = self.connector_manager.get_recent_notifications(limit=10)
        if not notifications:
            return "OpenCode n'a pas encore effectué d'action."
        
        summary = []
        for n in notifications:
            summary.append(f"[{n.get('type', 'info')}] {n.get('content', '')}")
        
        return "Dernières actions d'OpenCode :\n" + "\n".join(summary)

    async def process_voice_command(self, voice_text: str, current_state: EditorState) -> List[Action]:
        """
        Point d'entrée spécifique pour les commandes vocales.
        Transforme le texte brut du STT en actions concrètes.
        """
        cleaned_text = voice_text.replace("euh", "").replace("ah", "").strip()
        logger.info(f"Processing voice command: {cleaned_text}")
        
        return await self.process_user_intent(cleaned_text, current_state)

# Singleton pour le service d'intelligence
_intelligence_service: Optional[IntelligenceService] = None

def init_intelligence_service(planner, executor, connector_manager):
    global _intelligence_service
    _intelligence_service = IntelligenceService(planner, executor, connector_manager)
    return _intelligence_service

def get_intelligence_service() -> IntelligenceService:
    if _intelligence_service is None:
        raise RuntimeError("IntelligenceService is not initialized.")
    return _intelligence_service
