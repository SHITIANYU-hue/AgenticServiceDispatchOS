from __future__ import annotations
from typing import Tuple

# Minimal stub.
# In production: policy checks, forbidden promises, price consistency, escalation rules, etc.

def should_escalate(text: str) -> Tuple[bool, str]:
    keywords = ["投诉", "起诉", "报警", "退款", "差评", "威胁"]
    if any(k in text for k in keywords):
        return True, "high_risk_keywords"
    return False, ""
