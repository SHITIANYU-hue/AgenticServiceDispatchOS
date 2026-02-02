from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from .base import Repo
from .models import User, Lead, Chef, Offer, Booking, ConversationMessage, LeadStage

class InMemoryRepo(Repo):
    # In-memory storage for local/dev usage.
    def __init__(self):
        # Simple dict/list stores by id.
        self.users: dict[str, User] = {}
        self.leads: dict[str, Lead] = {}
        self.chefs: dict[str, Chef] = {}
        self.offers: dict[str, Offer] = {}
        self.bookings: dict[str, Booking] = {}
        self.messages: list[ConversationMessage] = []
        self.tool_call_logs: list[dict] = []

    def upsert_user(self, u: User) -> User:
        # Insert or replace user.
        self.users[u.user_id] = u
        return u

    def get_user_by_external(self, channel: str, external_id: str) -> Optional[User]:
        # Linear scan for channel + external_id.
        for u in self.users.values():
            if u.channel == channel and u.external_id == external_id:
                return u
        return None

    def create_lead(self, lead: Lead) -> Lead:
        # Insert new lead.
        self.leads[lead.lead_id] = lead
        return lead

    def get_lead(self, lead_id: str) -> Optional[Lead]:
        # Fetch lead by id.
        return self.leads.get(lead_id)

    def get_active_lead(self, user_id: str) -> Optional[Lead]:
        # Latest non-terminal lead for a user.
        candidates = [
            l for l in self.leads.values()
            if l.user_id == user_id and l.stage not in (LeadStage.DONE, LeadStage.CANCELLED)
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: x.updated_at, reverse=True)
        return candidates[0]

    def update_lead(self, lead: Lead) -> Lead:
        # Update lead and bump timestamp.
        lead.updated_at = datetime.utcnow()
        self.leads[lead.lead_id] = lead
        return lead

    def list_chefs(self) -> List[Chef]:
        # Return all chefs.
        return list(self.chefs.values())

    def get_chef(self, chef_id: str) -> Optional[Chef]:
        # Fetch chef by id.
        return self.chefs.get(chef_id)

    def create_offer(self, offer: Offer) -> Offer:
        # Insert offer.
        self.offers[offer.offer_id] = offer
        return offer

    def update_offer(self, offer: Offer) -> Offer:
        # Persist offer updates.
        self.offers[offer.offer_id] = offer
        return offer

    def get_offer(self, offer_id: str) -> Optional[Offer]:
        # Fetch offer by id.
        return self.offers.get(offer_id)

    def get_offer_by_lead(self, lead_id: str) -> Optional[Offer]:
        # Latest offer by lead id.
        offers = [o for o in self.offers.values() if o.lead_id == lead_id]
        if not offers:
            return None
        offers.sort(key=lambda x: x.created_at, reverse=True)
        return offers[0]

    def list_offers(self, lead_id: str) -> List[Offer]:
        # All offers for a lead.
        return [o for o in self.offers.values() if o.lead_id == lead_id]

    def create_booking(self, booking: Booking) -> Booking:
        # Insert booking.
        self.bookings[booking.booking_id] = booking
        return booking

    def get_booking(self, booking_id: str) -> Optional[Booking]:
        # Fetch booking by id.
        return self.bookings.get(booking_id)

    def list_bookings_by_lead(self, lead_id: str) -> List[Booking]:
        # List bookings for a lead (newest first).
        bookings = [b for b in self.bookings.values() if b.lead_id == lead_id]
        bookings.sort(key=lambda x: x.created_at, reverse=True)
        return bookings

    def update_booking(self, booking: Booking) -> Booking:
        # Persist booking updates.
        self.bookings[booking.booking_id] = booking
        return booking

    def add_message(self, msg: ConversationMessage) -> ConversationMessage:
        # Append chat message.
        self.messages.append(msg)
        return msg

    def list_messages(self, user_id: str, limit: int = 50) -> List[ConversationMessage]:
        # Return most recent messages for a user.
        msgs = [m for m in self.messages if m.user_id == user_id]
        return msgs[-limit:]
