"""
OpsAgent workflow:
- Confirm payment via tools when user says they paid.
- Handle cancel/reschedule/refund via policy_engine.
- Otherwise create booking + payment link to move toward close.
"""
from __future__ import annotations
from typing import Dict, Any
from datetime import datetime
from app.aim.agent_base import BaseAgent, AgentContext
from app.storage.base import Repo
from app.domains.private_chef.state_machine import advance_lead
from app.domains.private_chef.policy_engine import refund_policy_reply, reschedule_policy_reply

class OpsAgent(BaseAgent):
    # Post-offer operations: booking + payment.
    name = "OpsAgent"

    def __init__(self, repo: Repo):
        # Repo used for lead/offer lookup.
        self.repo = repo

    def run(self, ctx: AgentContext, input_text: str, tools, **kwargs) -> Dict[str, Any]:
        # Flow:
        # 1) Confirm payment if user says they've paid.
        # 2) For cancel/refund/reschedule, respond via policy_engine.
        # 3) Otherwise create booking + payment link for deposit.
        # 4) Advance lead state after tool calls.
        lead = self.repo.get_active_lead(ctx.user_id)
        if not lead:
            return {"reply": "我这边没找到你的订单信息，能再提供一下联系方式或需求吗？"}

        booking_list = self.repo.list_bookings_by_lead(lead.lead_id)
        booking = booking_list[0] if booking_list else None
        # Short-circuit if payment is already settled or booking is confirmed.
        if booking and booking.status in ("DEPOSIT_PAID", "CONFIRMED"):
            if booking.status == "CONFIRMED":
                return {"reply": "档期已确认，如需改期/取消请告诉我。", "booking": booking.model_dump(), "lead": lead.model_dump()}
            return {"reply": "定金已确认到账，我会尽快为你安排主厨。", "booking": booking.model_dump(), "lead": lead.model_dump()}

        # Payment confirmation path.
        if any(k in input_text for k in ["已支付", "我付了", "支付完成", "已转账"]):
            booking_id = lead.last_booking_id
            if not booking_id:
                return {"reply": "我这边还没有你的锁档记录，先帮你生成支付链接好吗？"}
            booking_result = tools.call("confirm_deposit", ctx=ctx, booking_id=booking_id)
            if isinstance(booking_result, dict) and booking_result.get("ok") is False:
                # Demo fallback: simulate a successful payment confirmation.
                booking_obj = self.repo.get_booking(booking_id)
                if not booking_obj:
                    return {"reply": "我这边还没有你的锁档记录，先帮你生成支付链接好吗？"}
                booking_obj.status = "DEPOSIT_PAID"
                booking_obj.deposit_paid_at = datetime.utcnow()
                self.repo.update_booking(booking_obj)
                lead = advance_lead(lead, "DEPOSIT_PAID")
                self.repo.update_lead(lead)
                return {"reply": "已模拟确认定金到账，档期已锁定。（演示环境）", "booking": booking_obj.model_dump(), "lead": lead.model_dump()}
            lead = advance_lead(lead, "DEPOSIT_PAID")
            self.repo.update_lead(lead)
            return {"reply": "已确认定金到账，档期已锁定。我会尽快与主厨确认备餐细节。", "booking": booking_result, "lead": lead.model_dump()}

        # Policy-driven cancellations/refunds.
        if any(k in input_text for k in ["取消", "退款", "退定金"]):
            offer = self.repo.get_offer_by_lead(lead.lead_id)
            deposit = offer.deposit_cny if offer else 0
            policy = refund_policy_reply(deposit, input_text)
            return {"reply": policy["reply"], "policy": policy}

        # Policy-driven reschedule request.
        if any(k in input_text for k in ["改期", "改时间", "换时间", "改日期"]):
            policy = reschedule_policy_reply()
            return {"reply": policy["reply"], "policy": policy}

        offers = self.repo.list_offers(lead.lead_id)
        if not offers:
            return {"reply": "我需要先确认报价方案，再为你生成支付链接。"}

        offers.sort(key=lambda o: o.created_at, reverse=True)
        offer = offers[0]

        # Reuse existing hold if present; otherwise create a new booking.
        if booking and booking.status == "HOLD":
            booking_result = booking.model_dump()
        else:
            booking_result = tools.call(
                "create_booking",
                ctx=ctx,
                lead_id=lead.lead_id,
                offer_id=offer.offer_id,
                hold_minutes=60,
            )
        pay = tools.call(
            "create_payment_link",
            ctx=ctx,
            booking_id=booking_result["booking_id"],
            amount_cny=offer.deposit_cny,
        )
        if isinstance(pay, dict) and pay.get("ok") is False:
            return {"reply": "我这边生成支付链接时出了点问题，稍等我再试一下。"}

        lead = advance_lead(lead, "BOOKING_CREATED")
        self.repo.update_lead(lead)

        reply = (
            f"我帮你先锁档 60 分钟，定金 ¥{offer.deposit_cny/100:.0f}。"
            f"支付链接：{pay['pay_url']}。完成后我立刻确认档期。"
        )
        return {"reply": reply, "booking": booking_result, "payment": pay, "lead": lead.model_dump()}
