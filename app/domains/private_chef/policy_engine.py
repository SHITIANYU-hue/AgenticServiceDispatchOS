from __future__ import annotations
from typing import Dict, Optional
import re

# Minimal policy engine stub.
# In production: cancellation windows, refunds, reschedule fees, force majeure, etc.

def calc_refund(deposit: int, hours_before: int) -> Dict[str, object]:
    # Calculate refund amount based on hours-before policy.
    if hours_before >= 48:
        fee_rate = 0.0
        policy_tag = "FULL_REFUND"
    elif hours_before >= 24:
        fee_rate = 0.2
        policy_tag = "PARTIAL_REFUND"
    else:
        fee_rate = 1.0
        policy_tag = "NO_REFUND"

    refund_amount = max(0, int(deposit * (1 - fee_rate)))
    return {
        "refund_amount": refund_amount,
        "fee_rate": fee_rate,
        "policy_tag": policy_tag,
    }

def _parse_hours_before(text: str) -> Optional[int]:
    # Parse "X小时" or "X天" into hours.
    m = re.search(r"(\d+)\s*(小时|时)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(天)", text)
    if m:
        return int(m.group(1)) * 24
    return None

def refund_policy_reply(deposit: int, input_text: str) -> Dict[str, object]:
    # Build refund policy reply; asks for timing if missing.
    hours_before = _parse_hours_before(input_text)
    if hours_before is None:
        return {
            "ok": False,
            "reply": "为了按规则处理取消/退款，需要知道距离用餐时间还有多少小时（例如：48小时）。",
        }
    policy = calc_refund(deposit, hours_before)
    reply = (
        f"根据当前规则，距离用餐 {hours_before} 小时，"
        f"可退金额 ¥{policy['refund_amount']/100:.0f}（规则：{policy['policy_tag']}）。"
    )
    return {"ok": True, "reply": reply, "policy": policy}

def reschedule_policy_reply() -> Dict[str, object]:
    # Minimal reschedule policy response.
    return {
        "ok": True,
        "reply": "可以协助改期。请提供新的用餐时间与地点，我会按规则确认档期和可行方案。",
    }
