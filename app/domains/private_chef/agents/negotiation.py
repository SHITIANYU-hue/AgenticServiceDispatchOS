from __future__ import annotations
from typing import Dict, Any
from app.aim.agent_base import BaseAgent, AgentContext

class NegotiationAgent(BaseAgent):
    name = "NegotiationAgent"

    def run(self, ctx: AgentContext, input_text: str, tools, **kwargs) -> Dict[str, Any]:
        # Stub: implement floor/discount strategy + escalation later
        return {"reply": "我理解你希望更优惠～我可以给你一个更合适的方案：比如调整菜品结构或选择相近档期。你更在意价格还是口味/档期？"}
