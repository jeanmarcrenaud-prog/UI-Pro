# Agents/Planner - Strategic Planning Agent

import logging
import json
from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    step_id: int
    description: str
    status: str = "pending"
    result: str = None


@dataclass
class Plan:
    goal: str
    steps: List[PlanStep]
    created_at: datetime = field(default_factory=datetime.now)
    
    def mark_completed(self, step_id: int, result: str):
        for step in self.steps:
            if step.step_id == step_id:
                step.status = "completed"
                step.result = result
    
    def is_complete(self) -> bool:
        return all(s.status == "completed" for s in self.steps)


class Planner:
    """Strategic planner that breaks down goals into steps"""
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
    
    async def create_plan(self, goal: str, context: Dict = None) -> Plan:
        """Create a plan from a goal"""
        context = context or {}
        
        prompt = f"""You are a strategic planner.
Break down this goal into 4-8 ordered steps.

Goal: {goal}

Return ONLY valid JSON:
{{
  "goal": "...",
  "steps": [
    {{"step_id": 1, "description": "..."}},
    ...
  ]
}}"""
        
        try:
            response = await self.llm_service.generate(prompt, mode="reasoning")
            result = json.loads(response)
            
            steps = []
            for step_data in result.get("steps", []):
                steps.append(PlanStep(
                    step_id=step_data.get("step_id", len(steps) + 1),
                    description=step_data.get("description", "")
                ))
            
            plan = Plan(goal=result.get("goal", goal), steps=steps)
            logger.info(f"Created plan with {len(steps)} steps")
            return plan
        
        except Exception as e:
            logger.error(f"Plan creation failed: {e}")
            return Plan(goal=goal, steps=[PlanStep(1, goal)])