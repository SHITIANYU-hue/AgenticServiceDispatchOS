from __future__ import annotations

# Minimal stub.
# In production: state machine routing, tool plans, retries, human-in-the-loop.

def route_agent(stage: str) -> str:
    if stage in ("NEW", "INFO_GATHERING"):
        return "ReceptionAgent"
    if stage in ("OFFERING", "NEGOTIATING", "HOLDING_SLOT"):
        return "DispatchAgent"
    return "ReceptionAgent"
