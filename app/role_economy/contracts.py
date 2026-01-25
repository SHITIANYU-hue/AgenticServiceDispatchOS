from __future__ import annotations
from pydantic import BaseModel

class RepresentationContract(BaseModel):
    principal_type: str   # user/merchant/platform
    principal_id: str
    agent_role: str       # UserProxy/PlatformSales/...
    payout_rule: str      # minimal string; upgrade to structured later
