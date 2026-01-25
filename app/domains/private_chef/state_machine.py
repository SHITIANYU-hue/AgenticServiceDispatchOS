from __future__ import annotations
from app.storage.models import LeadStage

def next_stage(current: str, has_min_info: bool) -> str:
    if current == LeadStage.NEW:
        return LeadStage.INFO_GATHERING
    if current == LeadStage.INFO_GATHERING and has_min_info:
        return LeadStage.OFFERING
    return current
