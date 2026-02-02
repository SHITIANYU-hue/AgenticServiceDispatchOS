from __future__ import annotations
from typing import Dict, Any, List
from app.storage.models import Lead

_DEFAULT_DEPOSIT_RATE = 0.3
_DEFAULT_PER_PERSON_CNY = 30000  # ¥300 per person as a minimal baseline

def calc_deposit_cny(price_cny: int) -> int:
    # Default deposit rule (kept here as a business policy).
    return int(price_cny * _DEFAULT_DEPOSIT_RATE)

def _breakdown(price_cny: int) -> Dict[str, int]:
    # Simple fixed-ratio breakdown to keep demo consistent.
    food = int(price_cny * 0.7)
    service = int(price_cny * 0.2)
    transport = max(0, price_cny - food - service)
    return {"food": food, "service": service, "transport": transport}

def build_proposals(lead: Lead) -> List[Dict[str, Any]]:
    # Build a minimal 3-tier proposal list without chef assignment.
    people = lead.req.people or 1
    base_price = people * _DEFAULT_PER_PERSON_CNY
    budget = lead.req.budget_cny

    if budget:
        standard = max(base_price, budget)
        step = max(int(standard * 0.15), 10000)
        basic = max(base_price, standard - step)
        if basic == standard:
            standard = basic + step
        premium = standard + step
    else:
        step = max(int(base_price * 0.15), 10000)
        basic = base_price
        standard = base_price + step
        premium = base_price + 2 * step

    plans = [
        {
            "plan_id": "basic",
            "name": "基础",
            "price_cny": basic,
            "deposit_cny": calc_deposit_cny(basic),
            "items": ["方案: 基础", "前菜×1", "主菜×3", "甜品×1"],
            "highlights": ["6道菜", "经典搭配", "适合小型聚会"],
            "breakdown": _breakdown(basic),
        },
        {
            "plan_id": "standard",
            "name": "标准",
            "price_cny": standard,
            "deposit_cny": calc_deposit_cny(standard),
            "items": ["方案: 标准", "前菜×2", "主菜×4", "甜品×1"],
            "highlights": ["8道菜", "冷热搭配", "性价比最高"],
            "breakdown": _breakdown(standard),
        },
        {
            "plan_id": "premium",
            "name": "升级",
            "price_cny": premium,
            "deposit_cny": calc_deposit_cny(premium),
            "items": ["方案: 升级", "前菜×2", "主菜×5", "甜品×2"],
            "highlights": ["10道菜", "更高品质", "可适度定制"],
            "breakdown": _breakdown(premium),
        },
    ]
    return plans

def build_offer_quote(lead: Lead) -> Dict[str, Any]:
    # Backward-compatible single quote (use standard tier).
    plans = build_proposals(lead)
    standard = plans[1]
    return {
        "price_cny": standard["price_cny"],
        "deposit_cny": standard["deposit_cny"],
        "breakdown": standard["breakdown"],
    }
