# services/agents.py - Agent System with Multi-step Reasoning
#
# Agent system with:
# - Agent definitions
# - Multi-step reasoning (chain of thought)
# - Tool use
# - State management

import logging
import asyncio
import json
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent execution status"""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING_TOOL = "waiting_tool"
    COMPLETED = "completed"
    ERROR = "error"


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
    max_steps: int = 10
    timeout_seconds: int = 120
    verbose: bool = True
    use_tools: bool = True
    system_prompt: Optional[str] = None


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
        
        self.status = AgentStatus.IDLE
        self.steps: List[AgentStep] = []
        self._current_step = 0
        self._message_history: List[Dict] = []  # For multi-step reasoning
    
    async def run(self, task: str, context: Dict = None) -> Dict[str, Any]:
        """
        Run agent on a task.
        
        Args:
            task: Task description
            context: Additional context
            
        Returns:
            dict: {
                "status": AgentStatus,
                "result": str,
                "steps": List[AgentStep],
                "error": Optional[str]
            }
        """
        self.status = AgentStatus.THINKING
        self.steps = []
        self._current_step = 0
        
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
        
        try:
            # Main loop - proper ReAct cycle
            step_num = 0
            while step_num < self.config.max_steps:
                step_num += 1
                self._current_step = step_num
                
                # 1. THINK - Get next action from LLM with full context
                thought_response = await self._think_with_context(task, system_prompt)
                
                if not thought_response.get("action"):
                    break
                
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
                    
                    # Execute tool
                    tool_result = await self._execute_tool(tool_name, tool_args)
                    
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
            
            self.status = AgentStatus.COMPLETED
            return {
                "status": self.status.value,
                "result": result,
                "steps": [s.__dict__ for s in self.steps],
                "step_count": len(self.steps)
            }
            
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
    
    async def _think_with_context(self, task: str, system_prompt: str) -> Dict:
        """
        Think with full message history for proper ReAct cycle.
        
        This method builds on the message history accumulated across steps.
        """
        # Build context from message history
        context_messages = []
        for msg in self._message_history[-10:]:  # Last 10 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_messages.append(f"{role.upper()}: {content}")
        
        context_str = "\n".join(context_messages)
        
        prompt = f"""You are {self.config.name}, an AI assistant using ReAct reasoning.

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


# Predefined agents

def create_coder_agent(llm_service=None, tool_registry=None) -> Agent:
    """Create a coding agent"""
    return Agent(
        config=AgentConfig(
            name="CoderAgent",
            description="Agent specialized in writing and debugging code",
            max_steps=15,
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
    "get_agent",
    "create_coder_agent",
    "create_analyzer_agent"
]