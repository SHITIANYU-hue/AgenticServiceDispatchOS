from __future__ import annotations
from typing import Tuple

# Minimal guardrails for policy checks.
# In production: richer rules + model-based detection.

_BYPASS_PLATFORM = ["私下转账", "转微信", "加微信", "加v", "线下联系", "线下交易", "私下交易"]
_THREATS = ["投诉", "起诉", "报警", "曝光", "威胁", "差评"]
_IMPROPER_PROMISE = ["包退", "绝对保证", "保证退款", "一定能", "100%保证"]

_ACTION_PRIORITY = {
    "ESCALATE": 3,
    "HARD_REFUSE": 2,
    "SOFT_REFUSE": 1,
    "OK": 0,
}

def _match_any(text: str, keywords: list[str]) -> bool:
    # Simple substring match helper.
    return any(k in text for k in keywords)

def should_escalate(text: str) -> Tuple[bool, str, str]:
    # Return (flag, reason, action) for policy handling.
    reason = ""
    action = "OK"

    if _match_any(text, _THREATS):
        reason = "high_risk_threat"
        action = "ESCALATE"

    if _match_any(text, _BYPASS_PLATFORM):
        if _ACTION_PRIORITY["HARD_REFUSE"] > _ACTION_PRIORITY[action]:
            reason = "bypass_platform"
            action = "HARD_REFUSE"

    if _match_any(text, _IMPROPER_PROMISE):
        if _ACTION_PRIORITY["SOFT_REFUSE"] > _ACTION_PRIORITY[action]:
            reason = "improper_promise"
            action = "SOFT_REFUSE"

    return action != "OK", reason, action
