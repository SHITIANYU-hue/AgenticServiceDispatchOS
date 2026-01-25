from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.storage.base import Repo
from app.storage.models import Offer, Booking
from app.core.ids import new_id

def build_tools(repo: Repo) -> Dict[str, Any]:
    def extract_requirement(text: str) -> Dict[str, Any]:
        # Minimal extractor; replace with LLM + structured extraction later
        return {"notes": text}

    def check_availability(chef_id: str, date_time: str) -> Dict[str, Any]:
        chef = repo.get_chef(chef_id)
        ok = bool(chef and chef.availability.get(date_time, True))
        return {"available": ok, "chef_id": chef_id, "date_time": date_time}

    def make_offer(lead_id: str, chef_id: str, price_cny: int, deposit_cny: int, items: List[str]) -> Dict[str, Any]:
        offer = Offer(
            offer_id=new_id("offer"),
            lead_id=lead_id,
            chef_id=chef_id,
            price_cny=price_cny,
            deposit_cny=deposit_cny,
            items=items,
        )
        repo.create_offer(offer)
        return offer.model_dump()

    def create_booking(lead_id: str, offer_id: str, hold_minutes: int = 60) -> Dict[str, Any]:
        booking = Booking(
            booking_id=new_id("book"),
            lead_id=lead_id,
            offer_id=offer_id,
            status="HOLD",
            hold_until=datetime.utcnow() + timedelta(minutes=hold_minutes),
        )
        repo.create_booking(booking)
        return booking.model_dump()

    def create_payment_link(booking_id: str, amount_cny: int) -> Dict[str, Any]:
        return {"booking_id": booking_id, "pay_url": f"https://pay.mock/{booking_id}?amt={amount_cny}"}

    return {
        "extract_requirement": extract_requirement,
        "check_availability": check_availability,
        "make_offer": make_offer,
        "create_booking": create_booking,
        "create_payment_link": create_payment_link,
    }
