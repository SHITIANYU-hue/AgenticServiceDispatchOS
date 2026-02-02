from __future__ import annotations
"""
NegotiationAgent workflow:
- Call pricing_rules for counter pricing (never below floor).
- Offer alternatives when price cannot drop.
- Trigger guardrails when needed.
"""
from typing import Dict, Any
from app.aim.agent_base import BaseAgent, AgentContext
from app.aim.guardrails import should_escalate
from app.aim.llm.composer import compose_reply
from app.aim.llm.registry import LLMRegistry
from app.storage.base import Repo
from app.domains.private_chef.state_machine import advance_lead
from app.domains.private_chef.pricing_rules import counter_offer

class NegotiationAgent(BaseAgent):
    # Handles price bargaining and counter-offers.
    name = "NegotiationAgent"

    def __init__(self, repo: Repo, llm_registry: LLMRegistry | None = None, max_discount_rate: float = 0.1):
        # Repo access and discount guardrail.
        self.repo = repo
        self.llm_registry = llm_registry
        self.max_discount_rate = max_discount_rate

    def run(self, ctx: AgentContext, input_text: str, tools, **kwargs) -> Dict[str, Any]:
        # Flow:
        # 1) Run guardrails when needed (no off-platform or risky promises).
        # 2) Load latest offer and call pricing_rules for counter-offer.
        # 3) Enforce floor price and propose alternatives if no discount possible.
        # 4) Persist stage changes and return a next-step reply.
        lead = self.repo.get_active_lead(ctx.user_id)
        if not lead:
            return {"reply": "我这边没找到你的需求单，能再描述一下预算/人数/时间吗？"}

        flag, reason, action = should_escalate(input_text)
        if action in ("ESCALATE", "HARD_REFUSE", "SOFT_REFUSE"):
            reply = (
                f"我理解你的诉求。这个情况我先帮你转人工同事跟进（原因：{reason}）。"
                if action == "ESCALATE"
                else "为了保障双方权益，平台外的私下交易/联系我无法协助。我们可以继续在平台内沟通。"
                if action == "HARD_REFUSE"
                else "我理解你的期待，但我不能做出超出平台规则的保证。我们可以根据规则提供可行方案。"
            )
            return {"reply": reply, "escalated": action == "ESCALATE", "reason": reason, "action": action}

        offer = self.repo.get_offer_by_lead(lead.lead_id)
        if not offer:
            return {"reply": "我需要先给你一个基础报价方案，再根据你的预算做优化。你期望的预算区间是多少？"}

        chef = self.repo.get_chef(offer.chef_id) if offer.chef_id else None
        quote = counter_offer(offer, chef, input_text, max_discount_rate=self.max_discount_rate)

        # If we cannot lower price, offer alternative levers instead.
        if quote["counter_price_cny"] >= offer.price_cny:
            reply = (
                "我理解你希望更优惠～当前价格已接近成本线。"
                "我们可以通过调整菜品结构/档期来优化总价。"
                "你更在意价格还是菜品品质/档期？"
            )
            reply = compose_reply(
                self.llm_registry,
                self.name,
                input_text,
                {"lead": lead.model_dump(), "offer": offer.model_dump(), "alternatives": quote["alternatives"]},
                reply,
            )
            return {"reply": reply, "offer": offer.model_dump(), "alternatives": quote["alternatives"]}

        # Create a new offer with the counter price.
        counter_offer = tools.call(
            "make_offer",
            ctx=ctx,
            lead_id=lead.lead_id,
            chef_id=offer.chef_id,
            price_cny=quote["counter_price_cny"],
            deposit_cny=quote["deposit_cny"],
            items=offer.items or ["前菜", "主菜", "甜品"],
        )
        if isinstance(counter_offer, dict) and counter_offer.get("ok") is False:
            return {"reply": "我这边调整方案时出了点问题，稍等我再试一下。"}

        # Move lead into negotiating state and persist.
        lead = advance_lead(lead, "NEGOTIATION_STARTED")
        lead.last_offer_id = counter_offer.get("offer_id")
        self.repo.update_lead(lead)

        reply = (
            f"我可以帮你做到 ¥{quote['counter_price_cny']/100:.0f}，并保持核心菜品体验。"
            "如果可以的话，我帮你锁定这个方案？"
        )
        reply = compose_reply(
            self.llm_registry,
            self.name,
            input_text,
            {"lead": lead.model_dump(), "offer": counter_offer, "alternatives": quote["alternatives"]},
            reply,
        )
        return {"reply": reply, "offer": counter_offer, "lead": lead.model_dump()}
