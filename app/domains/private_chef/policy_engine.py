from __future__ import annotations

# Minimal policy engine stub.
# In production: cancellation windows, refunds, reschedule fees, force majeure, etc.

def calc_cancellation_fee(days_before: int) -> float:
    if days_before >= 3:
        return 0.0
    if days_before >= 1:
        return 0.2
    return 0.5
