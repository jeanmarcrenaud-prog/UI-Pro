import asyncio
import logging
import json
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from backend.domain.core.models import Action, EditorState, DelegateAction
from backend.domain.core.action_executor import ActionExecutor

logger = logging.getLogger(__name__)

class TaskPlanner:
    def __init__(
        self,
        model_name: str = "local-model",
        base_url: str = "http://localhost:1234/v1", # LM Studio default
        api_key: str = "lm-studio",
        prompt_path: str = "backend/prompts/planner_system_prompt.md"
    ):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name
        self.prompt_path = prompt_path
        self.system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file {self.prompt_path} not found. Using fallback.")
            return "You are a helpful coding assistant. Return a JSON array of actions."

    async def generate_plan(self, intent_description: str, current_state: EditorState) -> List[Action]:
        """
        Analyzes the user intent and the current editor state to generate a sequence 
        of actions. Uses an LLM to decide between atomic execution and delegation.
        """
        # Prepare the context from the current editor state
        context_str = (
            f"Active Files: {current_state.active_files}\n"
            f"Cursor Position: Line {current_state.cursor.line}, Column {current_state.cursor.column}\n"
            f"Selection: {current_state.selection if current_state.selection else 'None'}\n"
            f"Diagnostics: {current_state.diagnostics if current_state.diagnostics else 'None'}"
        )

        user_prompt = f"""
USER INTENT: {intent_description}

CONTEXT:
{context_str}

Please provide a JSON array of actions to fulfill this request.
"""

        logger.info(f"Requesting plan from LLM for: {intent_description}")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}, # Request JSON if model supports it
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            # Parse the JSON array
            # Note: Some models might wrap the JSON in code blocks, so we clean it.
            clean_content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_content)
            
            # The prompt asks for a list of actions, but some models might return { "actions": [...] }
            actions_data = data.get("actions", data.get("plan", data))
            if isinstance(actions_data, dict): # If it returned a single object instead of list
                actions_data = [actions_data]

            actions = []
            for item in actions_data:
                if "opencode_delegate" in item.get("action_type", "").lower():
                    actions.append(DelegateAction(
                        task=item.get("task", intent_description),
                        status="delegated"
                    ))
                else:
                    actions.append(Action(
                        action_type=item.get("action_type", "unknown"),
                        params=item.get("params", {}),
                        status="pending"
                    ))
            
            return actions

        except Exception as e:
            logger.error(f"LLM Planning Error: {e}")
            # Fallback: if LLM fails, try a simple heuristic or return empty
            return []

# Singleton for TaskPlanner
_task_planner: Optional[TaskPlanner] = None

async def init_task_planner(model_name: str = "local-model", base_url: str = "http://localhost:1234/v1"):
    global _task_planner
    _task_planner = TaskPlanner(model_name=model_name, base_url=base_url)
    return _task_planner

def get_task_planner() -> TaskPlanner:
    global _task_planner
    if _task_planner is None:
        # Fallback to a basic planner if not initialized
        from unittest.mock import MagicMock
        _task_planner = MagicMock(spec=TaskPlanner)
        _task_planner.generate_plan.return_value = []
    return _task_planner
