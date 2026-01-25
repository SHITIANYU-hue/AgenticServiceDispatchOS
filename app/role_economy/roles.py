from __future__ import annotations
from pydantic import BaseModel
from typing import List

class Permission(BaseModel):
    allow_tools: List[str] = []

class Role(BaseModel):
    role_name: str
    permission: Permission

ROLE_USER_PROXY = Role(role_name="UserProxy", permission=Permission(allow_tools=["extract_requirement"]))
ROLE_PLATFORM_SALES = Role(role_name="PlatformSales", permission=Permission(allow_tools=["check_availability","make_offer","create_booking","create_payment_link"]))
ROLE_MERCHANT_SERVICE = Role(role_name="MerchantService", permission=Permission(allow_tools=["check_availability"]))
