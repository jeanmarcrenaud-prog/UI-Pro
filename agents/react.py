# Agents/ReAct - ReAct Pattern Agent
# ReAct = Reasoning + Acting

import logging
from .agent import Agent, AgentConfig, AgentStatus

logger = logging.getLogger(__name__)


class ReActAgent(Agent):
    """
    ReAct (Reasoning + Acting) agent.
    Extended version with explicit reasoning steps.
    """
    
    def __init__(self, config: AgentConfig = None, llm_service=None, tool_manager=None):
        if config is None:
            config = AgentConfig(
                name="ReAct Agent",
                description="Reasoning + Acting agent",
                use_planning=True,
                max_steps=12,
            )
        super().__init__(config, llm_service, tool_manager)
        logger.info("ReActAgent initialized")