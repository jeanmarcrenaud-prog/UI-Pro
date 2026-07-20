from typing import List, Dict, Any, Optional, Union
from backend.domain.core.models import HermesAction, DelegateAction, EditorState
from backend.domain.core.editor_service import EditorService

import logging
logger = logging.getLogger(__name__)

class TaskPlanner:
    def __init__(self, editor_service: EditorService):
        self.editor_service = editor_service
        self.history: List[Dict[str, Any]] = []

    def generate_plan(self, goal: str, context: EditorState) -> List[Union[DelegateAction, HermesAction]]:
        logger.info(f"Planning for goal: {goal}")
        actions: List[Union[DelegateAction, HermesAction]] = []

        # Delegation detection - route to OpenCode
        delegate_keywords = ["opencode", "delegue", "coding", "implemente", "cree un", "bonjour"]
        if any(kw in goal.lower() for kw in delegate_keywords):
            actions.append(DelegateAction(
                action_type="opencode_delegate",
                task=goal,
                status="delegated",
            ))
            logger.info(f"Intent delegated to OpenCode: {goal}")
            return actions

        # Local planning (Hermes actions)
        if "bug" in goal.lower() or "erreur" in goal.lower():
            actions.append(HermesAction(
                action_type="comment_code",
                params={"start_line": 1, "start_col": 1, "end_line": 1, "end_col": 1, "comment_style": "// TODO: Debug"},
                reasoning="Added debug marker."
            ))

        actions.append(HermesAction(
            action_type="insert_code",
            params={
                "content": "print('Action planifiee par Hermes')",
                "line": context.cursor.line if context.cursor else 1,
                "col": context.cursor.column if context.cursor else 0
            },
            reasoning="Default insert action."
        ))
        return actions

    def refine_plan(self, current_plan: List[HermesAction], last_result: Dict[str, Any]) -> List[HermesAction]:
        if last_result.get("status") == "error":
            logger.warning(f"Action failed: {last_result.get('message')}")
        return current_plan
