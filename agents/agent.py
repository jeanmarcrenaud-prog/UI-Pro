# Agents - Agent System
# Core agent implementation with ReAct pattern

import logging
import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING_TOOL = "waiting_tool"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentStep:
    step_number: int
    thought: str
    action: Optional[str] = None
    observation: Optional[str] = None
    tool_used: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentConfig:
    name: str = "Agent"
    description: str = "AI Agent with ReAct pattern"
    max_steps: int = 10
    timeout_seconds: int = 120
    verbose: bool = True
    use_tools: bool = True
    use_planning: bool = False
    system_prompt: Optional[str] = None
    max_tool_calls_per_step: int = 3
    max_total_tool_calls: int = 20


class Agent:
    """
    Agent with multi-step reasoning (ReAct pattern).
    Pattern: Thought → Action → Observation → ...
    """
    
    def __init__(
        self, 
        config: AgentConfig, 
        llm_service: object = None, 
        tool_manager: object = None
    ):
        self.config = config
        self.llm_service = llm_service
        self.tool_manager = tool_manager
        self._planner: Planner | None = None
        
        if config.use_planning:
            from .planner import Planner
            self._planner = Planner(llm_service)
        
        self.status = AgentStatus.IDLE
        self.steps: List[AgentStep] = []
        self._current_step = 0
        self._message_history: list[dict[str, str]] = []
        self._execution_log: list[dict[str, Any]] = []
    
    def _log_event(self, event_type: str, data: Dict):
        self._execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            **data
        })
        if self.config.verbose:
            logger.info(f"[{event_type}] {data}")
    
    def _add_step(self, thought: str, action: str = None, observation: str = None, tool: str = None):
        step = AgentStep(
            step_number=len(self.steps) + 1,
            thought=thought,
            action=action,
            observation=observation,
            tool_used=tool
        )
        self.steps.append(step)
        return step
    
    async def run(self, task: str, context: Dict = None) -> Dict[str, Any]:
        """Run agent on task"""
        start_time = time.time()
        self._execution_log = []
        self._log_event("agent_start", {"task": task[:100]})
        
        context = context or {}
        current_plan = None
        
        # Planning phase
        if self.config.use_planning and self._planner:
            self.status = AgentStatus.PLANNING
            self._log_event("planning_start", {})
            current_plan = await self._planner.create_plan(task, context)
            self._log_event("plan_created", {"steps": len(current_plan.steps)})
        
        self.status = AgentStatus.THINKING
        system_prompt = self._build_system_prompt()
        
        self._message_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]
        
        total_tool_calls = 0
        
        try:
            for step_num in range(1, self.config.max_steps + 1):
                if total_tool_calls >= self.config.max_total_tool_calls:
                    self._log_event("safety_limit", {"tool_calls": total_tool_calls})
                    break
                
                # Think
                thought = await self._think()
                self._add_step(thought=thought)
                
                # Act
                result = await self._act(thought, current_plan)
                
                if result.get("final_response"):
                    self.status = AgentStatus.COMPLETED
                    return self._build_result(result["final_response"], current_plan)
                
                if result.get("tool_used"):
                    total_tool_calls += 1
            
            self.status = AgentStatus.ERROR
            return self._build_result("Max steps reached", current_plan, error="Max iterations")
        
        except asyncio.TimeoutError:
            return self._build_result("Timeout", current_plan, error="Timeout")
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return self._build_result("Error", current_plan, error=str(e))
    
    async def _think(self) -> str:
        """Thought phase"""
        try:
            response = await self.llm_service.generate(
                messages=self._message_history,
                mode="reasoning"
            )
            thought = response.get("content", "")
            self._message_history.append({"role": "assistant", "content": thought})
            return thought
        except Exception as e:
            logger.error(f"Think failed: {e}")
            return "Thinking..."
    
    async def _act(self, thought: str, plan) -> Dict:
        """Act phase - return final response or tool call"""
        if "final" in thought.lower() or len(self.steps) > 8:
            return {"final_response": thought}
        return {"tool_used": True, "result": "Tool executed"}
    
    def _build_system_prompt(self) -> str:
        return f"""You are {self.config.name}.
{self.config.description}

Use ReAct pattern: Thought → Action → Observation."""
    
    def _build_result(self, result: str, plan, error: str = None) -> Dict:
        return {
            "status": self.status.value,
            "result": result,
            "steps": [{"n": s.step_number, "t": s.thought} for s in self.steps],
            "plan": {"goal": plan.goal, "steps": len(plan.steps)} if plan else None,
            "execution_log": self._execution_log,
            "error": error,
            "metadata": {"steps": len(self.steps)}
        }