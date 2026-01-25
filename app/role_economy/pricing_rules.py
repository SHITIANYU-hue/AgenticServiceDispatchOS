from __future__ import annotations
from pydantic import BaseModel

class PricingRule(BaseModel):
    # minimal: set floor and max discount rate
    floor_cny: int
    max_discount_rate: float = 0.15
