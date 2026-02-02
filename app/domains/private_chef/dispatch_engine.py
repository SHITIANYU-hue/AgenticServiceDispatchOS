from __future__ import annotations
from typing import List, Dict, Any
from app.storage.models import Chef, Lead

def rank_chefs(lead: Lead, chefs: List[Chef]) -> List[Dict[str, Any]]:
    # Scored ranking with reasons for traceable selection.
    results: List[Dict[str, Any]] = []
    req = lead.req
    for c in chefs:
        score = 0.0
        reasons: List[str] = []

        # People fit
        if req.people:
            if req.people <= c.max_people:
                score += 2.0
                reasons.append("人数匹配")
            else:
                score -= 3.0
                reasons.append("人数超出")

        # Budget fit
        if req.budget_cny:
            if c.base_price_cny <= req.budget_cny:
                score += 2.5
                reasons.append("预算匹配")
            else:
                score -= 2.0
                reasons.append("预算偏高")

        # Availability (no specific time -> neutral)
        if req.date_time:
            available = c.availability.get(req.date_time, True)
            if available:
                score += 1.5
                reasons.append("档期可用")
            else:
                score -= 3.0
                reasons.append("档期冲突")

        # Rating
        score += c.rating
        if c.rating >= 4.7:
            reasons.append("评分高")

        results.append({"chef": c, "score": score, "reasons": reasons})

    # Stable order: higher score first, then higher rating, then lower price
    results.sort(
        key=lambda x: (-x["score"], -x["chef"].rating, x["chef"].base_price_cny)
    )
    return results
