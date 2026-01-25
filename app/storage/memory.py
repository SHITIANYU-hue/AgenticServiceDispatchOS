from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from .base import Repo
from .models import User, Lead, Chef, Offer, Booking, ConversationMessage, LeadStage

class InMemoryRepo(Repo):
    def __init__(self):
        self.users: dict[str, User] = {}
        self.leads: dict[str, Lead] = {}
        self.chefs: dict[str, Chef] = {}
        self.offers: dict[str, Offer] = {}
        self.bookings: dict[str, Booking] = {}
        self.messages: list[ConversationMessage] = []

    def upsert_user(self, u: User) -> User:
        self.users[u.user_id] = u
        return u

    def get_user_by_external(self, channel: str, external_id: str) -> Optional[User]:
        for u in self.users.values():
            if u.channel == channel and u.external_id == external_id:
                return u
        return None

    def create_lead(self, lead: Lead) -> Lead:
        self.leads[lead.lead_id] = lead
        return lead

    def get_active_lead(self, user_id: str) -> Optional[Lead]:
        candidates = [
            l for l in self.leads.values()
            if l.user_id == user_id and l.stage not in (LeadStage.DONE, LeadStage.CANCELLED)
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: x.updated_at, reverse=True)
        return candidates[0]

    def update_lead(self, lead: Lead) -> Lead:
        lead.updated_at = datetime.utcnow()
        self.leads[lead.lead_id] = lead
        return lead

    def list_chefs(self) -> List[Chef]:
        return list(self.chefs.values())

    def get_chef(self, chef_id: str) -> Optional[Chef]:
        return self.chefs.get(chef_id)

    def create_offer(self, offer: Offer) -> Offer:
        self.offers[offer.offer_id] = offer
        return offer

    def list_offers(self, lead_id: str) -> List[Offer]:
        return [o for o in self.offers.values() if o.lead_id == lead_id]

    def create_booking(self, booking: Booking) -> Booking:
        self.bookings[booking.booking_id] = booking
        return booking

    def get_booking(self, booking_id: str) -> Optional[Booking]:
        return self.bookings.get(booking_id)

    def update_booking(self, booking: Booking) -> Booking:
        self.bookings[booking.booking_id] = booking
        return booking

    def add_message(self, msg: ConversationMessage) -> ConversationMessage:
        self.messages.append(msg)
        return msg

    def list_messages(self, user_id: str, limit: int = 50) -> List[ConversationMessage]:
        msgs = [m for m in self.messages if m.user_id == user_id]
        return msgs[-limit:]
