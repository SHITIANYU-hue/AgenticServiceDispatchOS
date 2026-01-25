from __future__ import annotations
from typing import Dict, Any
from app.aim.agent_base import BaseAgent, AgentContext

class OpsAgent(BaseAgent):
    name = "OpsAgent"

    def run(self, ctx: AgentContext, input_text: str, tools, **kwargs) -> Dict[str, Any]:
        # Stub: confirmation, reminders, exception handling
        return {"reply": "我已记录～临近用餐前我会再次确认地址/联系人/到达时间等信息。"}
