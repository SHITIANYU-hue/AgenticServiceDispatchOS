from __future__ import annotations
from typing import Dict, Any, Optional
import re
from app.storage.models import Offer, Chef
from app.domains.private_chef.proposal_engine import calc_deposit_cny

_DEFAULT_MAX_DISCOUNT_RATE = 0.1

def _extract_budget_hint_cny(text: str) -> Optional[int]:
    # Extract budget hint in yuan and convert to fen.
    m = re.findall(r"\d{2,6}", text)
    if not m:
        return None
    return int(m[-1]) * 100

def counter_offer(
    offer: Offer,
    chef: Optional[Chef],
    input_text: str,
    max_discount_rate: Optional[float] = None,
) -> Dict[str, Any]:
    # Compute counter price within floor and discount policy.
    max_discount_rate = max_discount_rate if max_discount_rate is not None else _DEFAULT_MAX_DISCOUNT_RATE
    budget_hint_cny = _extract_budget_hint_cny(input_text)
    floor_price = chef.base_price_cny if chef else offer.price_cny
    discounted_price = int(offer.price_cny * (1 - max_discount_rate))
    target_price = budget_hint_cny if budget_hint_cny is not None else discounted_price
    counter_price = max(floor_price, min(offer.price_cny, target_price))

    return {
        "budget_hint_cny": budget_hint_cny,
        "floor_price_cny": floor_price,
        "counter_price_cny": counter_price,
        "deposit_cny": calc_deposit_cny(counter_price),
        "alternatives": [
            "调整菜品结构降低成本",
            "更换档期拿到更好价格",
            "推荐同类型评分高但更实惠的厨师",
        ],
    }
