from __future__ import annotations
"""
DispatchAgent workflow:
- Call dispatch_engine to rank chefs.
- Assign a concrete chef to an accepted offer.
- Confirm fulfillment readiness.
"""
from typing import Dict, Any
from datetime import datetime
from app.aim.agent_base import BaseAgent, AgentContext
from app.aim.llm.composer import compose_reply
from app.aim.llm.registry import LLMRegistry
from app.storage.base import Repo
from app.domains.private_chef.state_machine import advance_lead
from app.domains.private_chef.dispatch_engine import rank_chefs

class DispatchAgent(BaseAgent):
    # Dispatch agent that assigns a specific chef.
    name = "DispatchAgent"

    def __init__(self, repo: Repo, llm_registry: LLMRegistry | None = None):
        # Repo used for lead/chef lookup.
        self.repo = repo
        self.llm_registry = llm_registry

    def run(self, ctx: AgentContext, input_text: str, tools, **kwargs) -> Dict[str, Any]:
        # Flow:
        # 1) Load latest offer and booking status.
        # 2) If deposit paid, assign a chef via dispatch_engine.
        # 3) Confirm fulfillment and advance state.
        lead = self.repo.get_active_lead(ctx.user_id)
        if not lead:
            return {"reply": "我这边没找到你的需求单，能再描述一下人数/时间/预算吗？"}

        offer_obj = self.repo.get_offer_by_lead(lead.lead_id)
        if not offer_obj:
            return {"reply": "我需要先给你生成可成交方案，再为你安排主厨。"}

        if offer_obj.chef_id:
            chef = self.repo.get_chef(offer_obj.chef_id)
            chef_name = chef.name if chef else "主厨"
            return {"reply": f"已为你安排 {chef_name}，档期确认中。", "offer": offer_obj.model_dump(), "lead": lead.model_dump()}

        booking_list = self.repo.list_bookings_by_lead(lead.lead_id)
        booking = booking_list[0] if booking_list else None
        if not booking or booking.status != "DEPOSIT_PAID":
            return {"reply": "收到～定金确认后我会立即为你安排主厨。"}

        chefs = self.repo.list_chefs()
        candidates = rank_chefs(lead, chefs)
        if not candidates:
            return {"reply": "暂时没有完全匹配你预算/人数的大厨。我可以推荐相近方案或你想调整预算/档期？"}

        chef = candidates[0]["chef"]
        offer_obj.chef_id = chef.chef_id
        self.repo.update_offer(offer_obj)

        booking.status = "CONFIRMED"
        booking.confirmed_at = datetime.utcnow()
        self.repo.update_booking(booking)

        lead = advance_lead(lead, "DISPATCHED")
        self.repo.update_lead(lead)

        reply = f"已为你安排 {chef.name}，档期已确认。我会同步主厨与你确认备餐细节。"
        reply = compose_reply(
            self.llm_registry,
            self.name,
            input_text,
            {
                "lead": lead.model_dump(),
                "chef": {"name": chef.name, "cuisines": chef.cuisines},
                "offer": offer_obj.model_dump(),
                "booking": booking.model_dump() if booking else None,
            },
            reply,
        )
        return {
            "reply": reply,
            "offer": offer_obj.model_dump(),
            "booking": booking.model_dump() if booking else None,
            "lead": lead.model_dump(),
        }
