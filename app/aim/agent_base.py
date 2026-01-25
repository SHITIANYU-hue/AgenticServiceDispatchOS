from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class AgentContext:
    user_id: str
    lead_id: str
    role: str
    tenant_id: str = "default"

class BaseAgent:
    name: str = "BaseAgent"

    def run(self, ctx: AgentContext, input_text: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError
