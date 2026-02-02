from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict
from datetime import datetime

MoneyCNY = int  # amount in fen (1/100 CNY)

class User(BaseModel):
    # End-user identity record.
    user_id: str
    channel: str
    external_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class LeadStage:
    # Lead lifecycle states for routing and business logic.
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
    # Structured intake fields extracted from user messages.
    date_time: Optional[str] = None
    people: Optional[int] = None
    location: Optional[str] = None
    budget_cny: Optional[MoneyCNY] = None
    cuisine: Optional[str] = None
    allergies: Optional[str] = None
    notes: Optional[str] = None
    # Explicit confirmation gate before proposal.
    confirmed: bool = False
    # Tracks whether a confirmation prompt was already shown.
    confirmation_requested: bool = False

class Lead(BaseModel):
    # Sales lead / inquiry record tied to a user.
    # a Lead is the sales opportunity / customer inquiry for a private‑chef request.
    lead_id: str
    user_id: str
    source: str
    stage: str = LeadStage.NEW
    req: RequirementCard = Field(default_factory=RequirementCard)
    last_offer_id: Optional[str] = None
    last_booking_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Chef(BaseModel):
    # Chef profile with pricing and availability.
    chef_id: str
    name: str
    cuisines: List[str]
    base_price_cny: MoneyCNY
    service_radius_km: int
    max_people: int
    availability: Dict[str, bool] = Field(default_factory=dict)  # date_time -> available
    rating: float = 4.7

class Offer(BaseModel):
    # Proposal/quote generated for a lead.
    offer_id: str
    lead_id: str
    chef_id: Optional[str] = None
    price_cny: MoneyCNY
    deposit_cny: MoneyCNY
    currency: str = "CNY"
    breakdown: Dict[str, MoneyCNY] = Field(default_factory=dict)
    items: List[str] = Field(default_factory=list)
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Booking(BaseModel):
    # Reservation created from an offer.
    booking_id: str
    lead_id: str
    offer_id: str
    status: Literal["HOLD", "DEPOSIT_PAID", "CONFIRMED", "CANCELLED"] = "HOLD"
    hold_until: Optional[datetime] = None
    deposit_paid_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ConversationMessage(BaseModel):
    # Chat transcript record for audit and context.
    msg_id: str
    user_id: str
    lead_id: Optional[str] = None
    role: Literal["user", "agent", "system"] = "user"
    text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
