from __future__ import annotations
from typing import Dict, Any
from app.aim.agent_base import BaseAgent, AgentContext
from app.storage.base import Repo
from app.storage.models import LeadStage
from app.domains.private_chef.dispatch_engine import rank_chefs

class DispatchAgent(BaseAgent):
    name = "DispatchAgent"

    def __init__(self, repo: Repo):
        self.repo = repo

    def run(self, ctx: AgentContext, input_text: str, tools, **kwargs) -> Dict[str, Any]:
        lead = self.repo.get_active_lead(ctx.user_id)
        chefs = self.repo.list_chefs()
        cand = rank_chefs(lead, chefs)[:3]

        if not cand:
            return {"reply": "暂时没有完全匹配你预算/人数的大厨。我可以推荐相近方案或你想调整预算/档期？"}

        chef = cand[0]
        price = max(chef.base_price_cny, (lead.req.budget_cny or chef.base_price_cny))
        deposit = int(price * 0.3)

        offer = tools.call(
            "make_offer",
            lead_id=lead.lead_id,
            chef_id=chef.chef_id,
            price_cny=price,
            deposit_cny=deposit,
            items=["前菜", "主菜", "甜品"],
        )

        lead.stage = LeadStage.OFFERING
        self.repo.update_lead(lead)

        reply = (
            f"给你推荐 {chef.name}（擅长：{', '.join(chef.cuisines)}）。"
            f"参考价 ¥{offer['price_cny']/100:.0f}，定金 ¥{offer['deposit_cny']/100:.0f} 可锁档。"
            "你希望用餐时间大概是？我帮你确认档期。"
        )
        return {"reply": reply, "offer": offer, "lead": lead.model_dump()}
