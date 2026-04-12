# services/agents.py - Agent System with Multi-step Reasoning
"""
DEPRECATED: Use agents/agent.py instead.

Legacy agent system kept for backward compatibility.
If you're starting new work, use:
    from agents.agent import Agent, AgentConfig, create_coder_agent
"""

# Agent system with:
# - Agent definitions
# - Multi-step reasoning (chain of thought)
# - Tool use
# - State management
# - Strategic planning (Planner)

import logging
import asyncio
import json
import time
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent execution status"""
    IDLE = "idle"
    PLANNING = "planning"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING_TOOL = "waiting_tool"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class PlanStep:
    """Single step in a plan"""
    step_id: int
    description: str
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class Plan:
    """Strategic plan with goal and steps"""
    goal: str
    steps: List[PlanStep]
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def mark_completed(self, step_id: int, result: str = None):
        """Mark a step as completed"""
        for step in self.steps:
            if step.step_id == step_id:
                step.status = "completed"
                step.result = result
                break
    
    def mark_failed(self, step_id: int, error: str):
        """Mark a step as failed"""
        for step in self.steps:
            if step.step_id == step_id:
                step.status = "failed"
                step.error = error
                break
    
    def get_pending_steps(self) -> List[PlanStep]:
        """Get all pending steps"""
        return [s for s in self.steps if s.status == "pending"]
    
    def is_complete(self) -> bool:
        """Check if plan is complete"""
        return all(s.status in ["completed", "failed"] for s in self.steps)


class Planner:
    """
    Strategic planner that creates execution plans.
    
    Features:
    - Goal decomposition
    - Step planning with dependencies
    - Plan validation
    - Execution tracking
    """
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
    
    async def create_plan(self, goal: str, context: Dict = None) -> Plan:
        """
        Create a strategic plan from a goal.
        
        Args:
            goal: The high-level goal to achieve
            context: Additional context for planning
            
        Returns:
            Plan: Strategic plan with decomposed steps
        """
        context = context or {}
        
        # Build planning prompt
        prompt = f"""You are a strategic planner. Break down this goal into clear, executable steps.

Goal: {goal}

Context:
{json.dumps(context, indent=2) if context else "No additional context"}

Respond with JSON:
{{
  "goal": "The main goal (same as input)",
  "steps": [
    {{"step_id": 1, "description": "First step description"}},
    {{"step_id": 2, "description": "Second step description"}},
    ...
  ],
  "estimated_steps": "Number of steps expected"
}}

Guidelines:
- Break down into 3-8 steps
- Each step should be actionable and specific
- Steps should have a logical order
- Later steps may depend on earlier ones"""
        
        try:
            from .model_service import get_model_service
            llm = get_model_service()
            response = llm.generate(prompt, mode="reasoning")
            
            # Parse response
            result = json.loads(response)
            
            steps = []
            for step_data in result.get("steps", []):
                steps.append(PlanStep(
                    step_id=step_data.get("step_id", len(steps) + 1),
                    description=step_data.get("description", ""),
                    status="pending"
                ))
            
            plan = Plan(
                goal=result.get("goal", goal),
                steps=steps
            )
            
            logger.info(f"Created plan with {len(steps)} steps for goal: {goal}")
            return plan
            
        except Exception as e:
            logger.error(f"Plan creation failed: {e}")
            # Return a simple single-step plan as fallback
            return Plan(
                goal=goal,
                steps=[PlanStep(step_id=1, description=goal)]
            )
    
    async def update_plan(self, plan: Plan, step_result: Dict) -> Plan:
        """
        Update plan based on step execution result.
        
        Args:
            plan: Current plan
            step_result: Result of executing a step
            
        Returns:
            Updated plan
        """
        step_id = step_result.get("step_id")
        success = step_result.get("success", False)
        result = step_result.get("result")
        error = step_result.get("error")
        
        if success:
            plan.mark_completed(step_id, result)
        else:
            plan.mark_failed(step_id, error)
        
        return plan


@dataclass
class AgentStep:
    """Single step in agent reasoning"""
    step_number: int
    thought: str  # Reasoning
    action: Optional[str] = None  # What was done
    observation: Optional[str] = None  # What was observed
    tool_used: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentConfig:
    """Agent configuration"""
    name: str
    description: str
    max_steps: int = 10  # Safety: max iterations to prevent infinite loops
    timeout_seconds: int = 120
    verbose: bool = True
    use_tools: bool = True
    use_planning: bool = False  # NEW: Enable strategic planning
    system_prompt: Optional[str] = None
    
    # Safety guards
    max_tool_calls_per_step: int = 3  # Max tools per step
    max_total_tool_calls: int = 20  # Total tool call budget


class Agent:
    """
    Agent with multi-step reasoning (ReAct pattern).
    
    Pattern: Thought → Action → Observation → ...
    
    Features:
    - Chain of thought reasoning
    - Tool use
    - Step-by-step execution
    - State tracking
    """
    
    def __init__(self, config: AgentConfig, llm_service=None, tool_registry=None, tool_manager=None):
        self.config = config
        self.llm_service = llm_service
        self.tool_registry = tool_registry
        self.tool_manager = tool_manager  # NEW: ToolManager support
        
        # Planning support
        self._planner = None
        if config.use_planning:
            self._planner = Planner(llm_service)
        
        self.status = AgentStatus.IDLE
        self.steps: List[AgentStep] = []
        self._current_step = 0
        self._message_history: List[Dict] = []  # For multi-step reasoning
        self._execution_log: List[Dict] = []  # For observability
    
    async def run(self, task: str, context: Dict = None) -> Dict[str, Any]:
        """
        Run agent on a task with optional strategic planning.
        
        Args:
            task: Task description
            context: Additional context
            
        Returns:
            dict: {
                "status": AgentStatus,
                "result": str,
                "steps": List[AgentStep],
                "plan": Plan (if use_planning=True),
                "execution_log": List[Dict],
                "error": Optional[str]
            }
        """
        start_time = time.time()
        
        # Initialize execution log for observability
        self._execution_log = []
        self._log_event("agent_start", {"task": task, "context": context})
        
        context = context or {}
        
        # Build system prompt
        system_prompt = self._build_system_prompt()
        
        # Initial thought
        self._add_step(thought=f"Task: {task}")
        
        # Initialize message history for multi-step reasoning
        self._message_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]
        
        current_plan = None
        
        # STRATEGIC PLANNING PHASE
        if self.config.use_planning and self._planner:
            self.status = AgentStatus.PLANNING
            self._log_event("planning_start", {"goal": task})
            
            current_plan = await self._planner.create_plan(task, context)
            self._log_event("plan_created", {
                "goal": current_plan.goal,
                "steps": [{"id": s.step_id, "desc": s.description} for s in current_plan.steps]
            })
            
            self.status = AgentStatus.THINKING
        
        # Initialize tool call counter for safety
        total_tool_calls = 0
        step_timeout = self.config.timeout_seconds / max(self.config.max_steps, 1)
        
        try:
            # Main loop - proper ReAct cycle with safety guards
            step_num = 0
            while step_num < self.config.max_steps:
                step_num += 1
                self._current_step = step_num
                
                # Safety: check total tool call limit
                if total_tool_calls >= self.config.max_total_tool_calls:
                    self._log_event("safety_limit", {"reason": "max_total_tool_calls reached", "tool_calls": total_tool_calls})
                    break
                
                # If we have a plan, get current step description
                current_step_desc = None
                if current_plan:
                    pending = current_plan.get_pending_steps()
                    if pending:
                        current_step_desc = pending[0].description
                        self._log_event("step_start", {"step_id": pending[0].step_id, "description": current_step_desc})
                
                # 1. THINK - Get next action from LLM with timeout
                try:
                    thought_response = await asyncio.wait_for(
                        self._think_with_context(task, system_prompt, current_step_desc),
                        timeout=step_timeout
                    )
                except asyncio.TimeoutError:
                    self._log_event("step_timeout", {"step": step_num, "timeout": step_timeout})
                    break
                
                if not thought_response.get("action"):
                    break
                
                step_start = time.time()
                
                action = thought_response["action"]
                self._add_step(
                    thought=thought_response.get("thought", ""),
                    action=action
                )
                
                # 2. ACT - Execute action (tool or respond)
                if self.config.use_tools and action.startswith("use_tool:"):
                    # Extract tool name and arguments
                    action_parts = action.replace("use_tool:", "").strip()
                    tool_name = action_parts.split()[0] if action_parts else ""
                    tool_args = thought_response.get("tool_args", {})
                    
                    # Safety: check tool calls per step limit
                    if self.config.max_tool_calls_per_step > 0:
                        # Execute tool with timeout (already handled by Tool)
                        tool_result = await self._execute_tool(tool_name, tool_args)
                        total_tool_calls += 1
                        self._log_event("tool_executed", {"tool": tool_name, "total_calls": total_tool_calls})
                    
                    # Add observation to history
                    observation_str = str(tool_result)
                    self._add_step(
                        action=f"Used tool: {tool_name}",
                        observation=observation_str,
                        tool_used=tool_name
                    )
                    
                    # Add tool result to message history for next iteration
                    self._message_history.append({
                        "role": "assistant", 
                        "content": f"Thought: {thought_response.get('thought', '')}\nAction: {action}\nObservation: {observation_str}"
                    })
                    
                    # Check if tool execution was successful
                    if tool_result.get("status") == "error":
                        # Continue but note the error
                        self.logger.warning(f"Tool {tool_name} failed: {tool_result.get('error')}")
                else:
                    # Just respond - we're done
                    self._message_history.append({
                        "role": "assistant",
                        "content": thought_response.get("thought", "")
                    })
                    break
                
                # Check if done
                if thought_response.get("done"):
                    break
            
            # Final result
            final_thought = self.steps[-1].thought if self.steps else ""
            result = final_thought or f"Completed {len(self.steps)} steps"
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.status = AgentStatus.COMPLETED
            
            response = {
                "status": self.status.value,
                "result": result,
                "steps": [s.__dict__ for s in self.steps],
                "step_count": len(self.steps),
                "duration_ms": duration_ms,
                "execution_log": self._execution_log
            }
            
            # Add plan if available
            if current_plan:
                current_plan.completed_at = datetime.now()
                response["plan"] = {
                    "goal": current_plan.goal,
                    "steps": [{"id": s.step_id, "description": s.description, "status": s.status} for s in current_plan.steps]
                }
            
            self._log_event("agent_complete", {"duration_ms": duration_ms, "steps": len(self.steps)})
            return response
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(f"Agent error: {e}")
            return {
                "status": self.status.value,
                "error": str(e),
                "steps": [s.__dict__ for s in self.steps]
            }
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for the agent"""
        base = self.config.system_prompt or f"""You are {self.config.name}, an AI agent.

You solve tasks step by step using the ReAct pattern:
1. Think about what to do
2. Take an action (use a tool or respond)
3. Observe the result
4. Repeat until done

Available tools:"""
        
        # Add tool descriptions
        if self.tool_registry:
            tools = self.tool_registry.list_tools()
            for tool_name in tools:
                tool = self.tool_registry.get(tool_name)
                base += f"\n- {tool.name}: {tool.description}"
        
        return base
    
    async def _think(self, task: str, system_prompt: str) -> Dict:
        """Get next thought/action from LLM"""
        # Build context from previous steps with proper format
        history_lines = []
        for step in self.steps[-5:]:  # Last 5 steps
            line = f"Step {step.step_number}: {step.thought}"
            if step.action:
                line += f" → Action: {step.action}"
            if step.observation:
                line += f" → Observation: {step.observation}"
            history_lines.append(line)
        
        history = "\n".join(history_lines) if history_lines else "No previous steps"
        
        # Check if we should use tools or respond
        prompt = f"""{system_prompt}

Task: {task}
Context:
{history}

Think step by step. Choose your next action:

Format your response as JSON:
{{
  "thought": "Your reasoning about what to do next",
  "action": "use_tool:<tool_name> or 'respond'",
  "tool_args": {{"param": "value"}} (only if action starts with use_tool:),
  "done": true/false
}}

Important:
- Use 'use_tool:tool_name' to use a tool
- Use 'respond' when you have the answer
- Only set done=true when you have a complete answer
- If you need more information, use a tool first"""
        
        return await self._call_llm(prompt)
    
    async def _think_with_context(self, task: str, system_prompt: str, current_step_desc: str = None) -> Dict:
        """
        Think with full message history for proper ReAct cycle.
        
        Args:
            task: The current task
            system_prompt: System prompt
            current_step_desc: Current plan step description (if planning enabled)
        """
        # Build context from message history
        context_messages = []
        for msg in self._message_history[-10:]:  # Last 10 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_messages.append(f"{role.upper()}: {content}")
        
        context_str = "\n".join(context_messages)
        
        # Add plan context if available
        plan_context = ""
        if current_step_desc:
            plan_context = f"\nCurrent plan step: {current_step_desc}\n"
        
        prompt = f"""You are {self.config.name}, an AI assistant using ReAct reasoning.{plan_context}

Available tools:
{self._get_tool_descriptions()}

Conversation so far:
{context_str}

Current task: {task}

Analyze the conversation and decide your next action.
Respond with JSON:
{{
  "thought": "Your reasoning about what to do next",
  "action": "use_tool:<tool_name> or 'respond'", 
  "tool_args": {{"param": "value"}} (only if using a tool),
  "done": true/false
}}

Remember:
- Use tools to gather information if needed
- Set done=true only when you have the final answer
- Each tool result becomes part of your reasoning context"""
        
        return await self._call_llm(prompt)
    
    def _get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions"""
        if not self.tool_registry:
            return "No tools available"
        
        lines = []
        for tool_name in self.tool_registry.list_tools():
            tool = self.tool_registry.get(tool_name)
            if tool:
                lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines) if lines else "No tools available"
    
    async def _call_llm(self, prompt: str) -> Dict:
        """Make LLM call with proper error handling"""
        try:
            from .model_service import get_model_service
            llm = get_model_service()
            response = llm.generate(prompt, mode="reasoning")
            
            # Try to parse JSON
            try:
                return json.loads(response)
            except:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{[^{}]*\}', response)
                if json_match:
                    return json.loads(json_match.group())
                return {"thought": response, "action": "respond", "done": True}
        except Exception as e:
            logger.error(f"LLM call error: {e}")
            return {"thought": str(e), "action": "respond", "done": True}
        
        # Call LLM
        try:
            from .model_service import get_model_service
            llm = get_model_service()
            response = llm.generate(prompt, mode="reasoning")
            
            # Parse JSON response
            try:
                return json.loads(response)
            except:
                return {"thought": response, "action": "respond", "done": True}
        except Exception as e:
            logger.error(f"LLM call error: {e}")
            return {"thought": str(e), "action": "respond", "done": True}
    
    async def _execute_tool(self, tool_name: str, args: Dict) -> Any:
        """Execute a tool"""
        if not self.tool_registry:
            return {"error": "No tool registry"}
        
        tool = self.tool_registry.get(tool_name)
        if not tool:
            return {"error": f"Tool not found: {tool_name}"}
        
        self.status = AgentStatus.WAITING_TOOL
        result = await tool.execute(args)
        self.status = AgentStatus.THINKING
        
        return result
    
    def _add_step(self, thought: str = None, action: str = None, observation: str = None, tool_used: str = None):
        """Add a step to the history"""
        step = AgentStep(
            step_number=self._current_step,
            thought=thought or "",
            action=action,
            observation=observation,
            tool_used=tool_used
        )
        self.steps.append(step)
    
    def _log_event(self, event_type: str, data: Dict = None) -> None:
        """Log execution event for observability"""
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "step": self._current_step,
            "data": data or {}
        }
        self._execution_log.append(event)
        
        # Also log via standard logger
        if self.config.verbose:
            self.logger.info(f"[{event_type}] {data}")


# Predefined agents

def create_coder_agent(llm_service=None, tool_registry=None, use_planning: bool = False) -> Agent:
    """Create a coding agent"""
    return Agent(
        config=AgentConfig(
            name="CoderAgent",
            description="Agent specialized in writing and debugging code",
            max_steps=15,
            use_planning=use_planning,  # Enable strategic planning
            system_prompt="""You are an expert coding agent.

You help write, debug, and improve code.
Think step by step:
1. Understand the problem
2. Plan the solution
3. Write the code
4. Verify it works

Use tools when helpful:
- calculator: for math calculations
- search_memory: for finding similar code
- get_time: for time-related info"""
        ),
        llm_service=llm_service,
        tool_registry=tool_registry
    )


def create_strategic_coder_agent(llm_service=None, tool_registry=None) -> Agent:
    """
    Create a strategic coding agent that uses planning.
    
    This agent first creates a plan, then executes step by step.
    """
    return create_coder_agent(llm_service, tool_registry, use_planning=True)


def create_analyzer_agent(llm_service=None, tool_registry=None) -> Agent:
    """Create an analysis agent"""
    return Agent(
        config=AgentConfig(
            name="AnalyzerAgent",
            description="Agent specialized in analyzing and reviewing code",
            max_steps=10,
            system_prompt="""You are an expert code analyst.

You analyze code for:
- Bugs and issues
- Security vulnerabilities
- Performance problems
- Code quality

Think step by step through the code."""
        ),
        llm_service=llm_service,
        tool_registry=tool_registry
    )


# Agent factory

_agent_registry: Dict[str, Agent] = {}


def get_agent(name: str = "coder", llm_service=None, tool_registry=None) -> Agent:
    """Get or create an agent by name"""
    global _agent_registry
    
    if name not in _agent_registry:
        if name == "coder":
            _agent_registry[name] = create_coder_agent(llm_service, tool_registry)
        elif name == "analyzer":
            _agent_registry[name] = create_analyzer_agent(llm_service, tool_registry)
        else:
            raise ValueError(f"Unknown agent: {name}")
    
    return _agent_registry[name]


__all__ = [
    "Agent",
    "AgentConfig",
    "AgentStep",
    "AgentStatus",
    "Plan",
    "PlanStep",
    "Planner",
    "get_agent",
    "create_coder_agent",
    "create_strategic_coder_agent",
    "create_analyzer_agent"
]