from __future__ import annotations
from typing import List
from app.storage.models import Chef, Lead

def rank_chefs(lead: Lead, chefs: List[Chef]) -> List[Chef]:
    # Minimal ranking: higher rating first, then lower price
    candidates = []
    for c in chefs:
        if lead.req.people and lead.req.people > c.max_people:
            continue
        if lead.req.budget_cny and c.base_price_cny > lead.req.budget_cny:
            continue
        candidates.append(c)
    candidates.sort(key=lambda x: (-x.rating, x.base_price_cny))
    return candidates
