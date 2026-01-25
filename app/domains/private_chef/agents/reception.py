from __future__ import annotations
from typing import Dict, Any
from app.aim.agent_base import BaseAgent, AgentContext
from app.storage.base import Repo
from app.storage.models import LeadStage

class ReceptionAgent(BaseAgent):
    name = "ReceptionAgent"

    def __init__(self, repo: Repo):
        self.repo = repo

    def run(self, ctx: AgentContext, input_text: str, tools, **kwargs) -> Dict[str, Any]:
        lead = self.repo.get_active_lead(ctx.user_id)
        extracted = tools.call("extract_requirement", text=input_text)

        lead.req.notes = extracted.get("notes", lead.req.notes)
        lead.stage = LeadStage.INFO_GATHERING
        self.repo.update_lead(lead)

        reply = "收到～我需要确认几个信息：用餐时间、人数、地点，以及大致预算（元）？"
        return {"reply": reply, "lead": lead.model_dump()}
