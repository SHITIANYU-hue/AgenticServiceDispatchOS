from __future__ import annotations
"""
Lead routing workflow for agent selection.

This router decides which agent should speak next, based on lead state and
artifacts (offers/bookings) plus the latest user intent. It does not mutate
state; it only returns (agent_name, reason) for traceability.

Typical flow:
1) Missing intake -> ReceptionAgent
2) Has intake but no offer -> ProposalAgent
3) Bargain intent -> NegotiationAgent
4) Deposit paid but not dispatched -> DispatchAgent
5) Booking exists -> OpsAgent

Note: This is a lightweight router; deeper business rules belong in
state_machine/policy/engine modules, not here.
"""
from typing import Tuple

from app.domains.private_chef.state_machine import is_min_info_ready, is_intake_confirmed
from app.storage.base import Repo
from app.storage.models import Lead

_BARGAIN_KEYWORDS = ["砍价", "便宜", "优惠", "折扣", "贵", "太贵", "降价", "能不能便宜", "可不可以便宜"]
_OPS_KEYWORDS = ["取消", "退款", "退定金", "改期", "改时间", "换时间", "改日期", "已支付", "我付了", "支付完成", "已转账"]

def _has_bargain_intent(text: str) -> bool:
    # Simple keyword heuristic for negotiation intent.
    return any(k in text for k in _BARGAIN_KEYWORDS)

def _has_ops_intent(text: str) -> bool:
    # Lightweight signals for post-offer ops handling.
    return any(k in text for k in _OPS_KEYWORDS)

def agent_role(agent_name: str) -> str:
    # Minimal mapping from agent to tool role.
    if agent_name == "ReceptionAgent":
        return "UserProxy"
    return "PlatformSales"

def route_agent(lead: Lead, input_text: str, repo: Repo) -> Tuple[str, str]:
    # Decide next agent based on info completeness and artifacts.
    if not is_min_info_ready(lead.req):
        # Intake incomplete: collect missing requirements.
        return "ReceptionAgent", "missing_min_info"
    if not is_intake_confirmed(lead.req):
        # Intake needs explicit user confirmation before proposal.
        return "ReceptionAgent", "intake_needs_confirmation"

    offer = repo.get_offer_by_lead(lead.lead_id)
    if not offer:
        # No offer yet: generate proposal after intake is complete.
        return "ProposalAgent", "no_offer_yet"

    if _has_bargain_intent(input_text):
        # User is negotiating price or discount.
        return "NegotiationAgent", "bargain_intent"

    if _has_ops_intent(input_text):
        # Ops actions like pay/cancel/reschedule.
        return "OpsAgent", "ops_intent"

    booking_list = repo.list_bookings_by_lead(lead.lead_id)
    if booking_list:
        latest = booking_list[0]
        if latest.status == "DEPOSIT_PAID" and (offer.chef_id is None):
            return "DispatchAgent", "deposit_paid_needs_dispatch"
        if latest.status == "CONFIRMED":
            # Keep follow-ups in dispatch flow after confirmation.
            return "DispatchAgent", "booking_confirmed"
        # If a booking exists, we should handle payment/ops next.
        return "OpsAgent", "booking_exists"

    # Default path: keep guiding via proposal.
    return "ProposalAgent", "default_proposal"
