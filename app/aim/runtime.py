from __future__ import annotations
from typing import Dict, Any
from .agent_base import BaseAgent, AgentContext
from .tools import ToolRegistry

class AgentRuntime:
    def __init__(self, tools: ToolRegistry):
        self.tools = tools
        self.agents: Dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        self.agents[agent.name] = agent

    def step(self, agent_name: str, ctx: AgentContext, input_text: str, **kwargs) -> Dict[str, Any]:
        if agent_name not in self.agents:
            raise ValueError(f"Agent not found: {agent_name}")
        agent = self.agents[agent_name]
        return agent.run(ctx, input_text, tools=self.tools, **kwargs)
