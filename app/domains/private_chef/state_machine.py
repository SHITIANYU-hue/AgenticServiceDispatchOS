from __future__ import annotations
"""
Lead state machine for the private-chef workflow.

Real flow overview (happy path):
1) NEW -> INFO_GATHERING when intake starts.
2) OFFERING when minimum requirement fields are ready and a proposal is generated.
3) NEGOTIATING if user starts bargaining.
4) HOLDING_SLOT once a booking/hold is created (usually during proposal).
5) DEPOSIT_PAID after payment is confirmed.
6) CONFIRMED after dispatch assigns a chef.
7) FULFILLING/DONE handled by downstream ops.

This module does not call tools or mutate storage directly. Agents call
advance_lead() after tool actions and then persist the updated lead to repo.
"""
from app.storage.models import LeadStage, RequirementCard, Lead

_STAGE_ORDER = [
    LeadStage.NEW,
    LeadStage.INFO_GATHERING,
    LeadStage.OFFERING,
    LeadStage.NEGOTIATING,
    LeadStage.HOLDING_SLOT,
    LeadStage.DEPOSIT_PAID,
    LeadStage.CONFIRMED,
    LeadStage.FULFILLING,
    LeadStage.DONE,
]

def is_min_info_ready(req: RequirementCard) -> bool:
    # Minimum fields required before generating offers.
    if not req:
        return False
    if not req.date_time or not req.location:
        return False
    if not req.people or req.people <= 0:
        return False
    if not req.budget_cny or req.budget_cny <= 0:
        return False
    return True

def is_intake_confirmed(req: RequirementCard) -> bool:
    # Intake is ready only after minimum info is present and user confirms.
    if not is_min_info_ready(req):
        return False
    return bool(getattr(req, "confirmed", False))

def missing_requirements(req: RequirementCard) -> list[str]:
    # Human-readable list of missing intake fields used in replies.
    missing: list[str] = []
    if not req or not req.date_time:
        missing.append("用餐时间")
    if not req or not req.people:
        missing.append("人数")
    if not req or not req.location:
        missing.append("地点")
    if not req or not req.budget_cny:
        missing.append("预算（元）")
    return missing

def apply_requirement_update(lead: Lead, extracted_req: dict) -> Lead:
    # Merge extracted requirement values into the lead card.
    for key, value in extracted_req.items():
        if value is None:
            continue
        if hasattr(lead.req, key):
            setattr(lead.req, key, value)
    return lead

def _advance_stage(current: str, target: str) -> str:
    # Guard against stage regressions or invalid transitions.
    if current == LeadStage.CANCELLED or current == LeadStage.DONE:
        return current
    if target == LeadStage.CANCELLED:
        return target
    if current not in _STAGE_ORDER or target not in _STAGE_ORDER:
        return current
    if _STAGE_ORDER.index(target) < _STAGE_ORDER.index(current):
        return current
    return target

def advance_lead(lead: Lead, event: str) -> Lead:
    # Event-driven stage transition entrypoint; do not persist here.
    if event == "INFO_UPDATED":
        # Intake may graduate to OFFERING once minimum fields exist.
        target = LeadStage.OFFERING if is_min_info_ready(lead.req) else LeadStage.INFO_GATHERING
        lead.stage = _advance_stage(lead.stage, target)
        return lead

    if event == "OFFER_CREATED":
        # Proposal/offer created; only move forward, never regress.
        lead.stage = _advance_stage(lead.stage, LeadStage.OFFERING)
        return lead

    if event == "NEGOTIATION_STARTED":
        # Negotiation is a parallel path from OFFERING.
        lead.stage = _advance_stage(lead.stage, LeadStage.NEGOTIATING)
        return lead

    if event == "BOOKING_CREATED":
        # Booking implies a hold on the chef slot.
        lead.stage = _advance_stage(lead.stage, LeadStage.HOLDING_SLOT)
        return lead

    if event == "DEPOSIT_PAID":
        # Deposit paid is a key commitment milestone.
        lead.stage = _advance_stage(lead.stage, LeadStage.DEPOSIT_PAID)
        return lead

    if event == "DISPATCHED":
        # Chef assigned and fulfillment confirmed.
        lead.stage = _advance_stage(lead.stage, LeadStage.CONFIRMED)
        return lead

    if event == "CANCELLED":
        # Terminal state; no further transitions.
        lead.stage = LeadStage.CANCELLED
        return lead

    return lead
