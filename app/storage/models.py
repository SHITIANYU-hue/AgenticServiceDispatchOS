from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict
from datetime import datetime

MoneyCNY = int  # amount in fen (1/100 CNY)

class User(BaseModel):
    user_id: str
    channel: str
    external_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class LeadStage:
    NEW = "NEW"
    INFO_GATHERING = "INFO_GATHERING"
    OFFERING = "OFFERING"
    NEGOTIATING = "NEGOTIATING"
    HOLDING_SLOT = "HOLDING_SLOT"
    DEPOSIT_PAID = "DEPOSIT_PAID"
    CONFIRMED = "CONFIRMED"
    FULFILLING = "FULFILLING"
    DONE = "DONE"
    CANCELLED = "CANCELLED"

class RequirementCard(BaseModel):
    date_time: Optional[str] = None
    people: Optional[int] = None
    location: Optional[str] = None
    budget_cny: Optional[MoneyCNY] = None
    cuisine: Optional[str] = None
    allergies: Optional[str] = None
    notes: Optional[str] = None

class Lead(BaseModel):
    lead_id: str
    user_id: str
    source: str
    stage: str = LeadStage.NEW
    req: RequirementCard = Field(default_factory=RequirementCard)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Chef(BaseModel):
    chef_id: str
    name: str
    cuisines: List[str]
    base_price_cny: MoneyCNY
    service_radius_km: int
    max_people: int
    availability: Dict[str, bool] = Field(default_factory=dict)  # date_time -> available
    rating: float = 4.7

class Offer(BaseModel):
    offer_id: str
    lead_id: str
    chef_id: str
    price_cny: MoneyCNY
    deposit_cny: MoneyCNY
    items: List[str] = Field(default_factory=list)
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Booking(BaseModel):
    booking_id: str
    lead_id: str
    offer_id: str
    status: Literal["HOLD", "DEPOSIT_PAID", "CONFIRMED", "CANCELLED"] = "HOLD"
    hold_until: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ConversationMessage(BaseModel):
    msg_id: str
    user_id: str
    lead_id: Optional[str] = None
    role: Literal["user", "agent", "system"] = "user"
    text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
