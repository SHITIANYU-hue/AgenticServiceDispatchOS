from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List
from .models import User, Lead, Chef, Offer, Booking, ConversationMessage

class Repo(ABC):
    # Storage interface for users/leads/offers/bookings/messages.
    @abstractmethod
    # Create or update a user record.
    def upsert_user(self, u: User) -> User: ...
    @abstractmethod
    # Fetch a user by external channel id.
    def get_user_by_external(self, channel: str, external_id: str) -> Optional[User]: ...

    @abstractmethod
    # Create a new lead.
    def create_lead(self, lead: Lead) -> Lead: ...
    @abstractmethod
    # Fetch a lead by id.
    def get_lead(self, lead_id: str) -> Optional[Lead]: ...
    @abstractmethod
    # Get the latest active lead for a user.
    def get_active_lead(self, user_id: str) -> Optional[Lead]: ...
    @abstractmethod
    # Persist lead updates.
    def update_lead(self, lead: Lead) -> Lead: ...

    @abstractmethod
    # List available chefs.
    def list_chefs(self) -> List[Chef]: ...
    @abstractmethod
    # Fetch a chef by id.
    def get_chef(self, chef_id: str) -> Optional[Chef]: ...

    @abstractmethod
    # Create an offer.
    def create_offer(self, offer: Offer) -> Offer: ...
    @abstractmethod
    # Persist offer updates.
    def update_offer(self, offer: Offer) -> Offer: ...
    @abstractmethod
    # Fetch an offer by id.
    def get_offer(self, offer_id: str) -> Optional[Offer]: ...
    @abstractmethod
    # Get the latest offer for a lead.
    def get_offer_by_lead(self, lead_id: str) -> Optional[Offer]: ...
    @abstractmethod
    # List all offers for a lead.
    def list_offers(self, lead_id: str) -> List[Offer]: ...

    @abstractmethod
    # Create a booking.
    def create_booking(self, booking: Booking) -> Booking: ...
    @abstractmethod
    # Fetch a booking by id.
    def get_booking(self, booking_id: str) -> Optional[Booking]: ...
    @abstractmethod
    # List bookings for a lead.
    def list_bookings_by_lead(self, lead_id: str) -> List[Booking]: ...
    @abstractmethod
    # Persist booking updates.
    def update_booking(self, booking: Booking) -> Booking: ...

    @abstractmethod
    # Append a conversation message.
    def add_message(self, msg: ConversationMessage) -> ConversationMessage: ...
    @abstractmethod
    # List recent messages for a user.
    def list_messages(self, user_id: str, limit: int = 50) -> List[ConversationMessage]: ...
