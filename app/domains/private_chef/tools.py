from __future__ import annotations
from datetime import datetime, timedelta
import logging
import re
from typing import Dict, Any, List, Optional
import json
from app.config import settings
from app.aim.llm.registry import LLMRegistry
from app.storage.base import Repo
from app.storage.models import Offer, Booking
from app.core.ids import new_id

logger = logging.getLogger(__name__)

def build_tools(repo: Repo, llm_registry: LLMRegistry | None = None) -> Dict[str, Any]:
    # Tool factory bound to a repo instance.
    def _parse_cn_number(num: str) -> Optional[int]:
        # Parse basic Chinese numerals (<= thousands).
        digit_map = {
            "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
        }
        unit_map = {"十": 10, "百": 100, "千": 1000}
        if not num:
            return None

        total = 0
        current = 0
        for ch in num:
            if ch in digit_map:
                current = digit_map[ch]
            elif ch in unit_map:
                unit = unit_map[ch]
                if current == 0:
                    current = 1
                total += current * unit
                current = 0
            else:
                return None
        total += current
        return total if total > 0 else None

    def _extract_people(text: str) -> Optional[int]:
        # Extract headcount from digits or Chinese numerals.
        m = re.search(r"(\d+)\s*(个|位)?\s*(人|位)", text)
        if m:
            return int(m.group(1))
        m_cn = re.search(r"([零一二两三四五六七八九十百千]+)\s*(个|位)?\s*(人|位)", text)
        if not m_cn:
            return None
        return _parse_cn_number(m_cn.group(1))

    def _extract_budget_yuan(text: str) -> Optional[int]:
        # Extract budget in yuan (supports "万" unit).
        m = re.search(r"(预算|大概|大约)?\s*(\d{2,7})(\s*万)?\s*(元|块|RMB|¥|￥)?", text)
        if not m:
            return None
        amount = int(m.group(2))
        if m.group(3):
            amount *= 10000
        return amount

    def _extract_date_time(text: str) -> Optional[str]:
        # Extract coarse time expressions.
        patterns = [
            r"\d{1,2}月\d{1,2}日(?:早上|上午|中午|下午|晚上|晚间|夜里)?\d{0,2}点?",
            r"(今天|明天|后天)(?:早上|上午|中午|下午|晚上|晚间|夜里)?\d{0,2}点?",
            r"(周[一二三四五六日天])(?:早上|上午|中午|下午|晚上|晚间|夜里)?\d{0,2}点?",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(0)
        return None

    def _extract_location(text: str) -> Optional[str]:
        # Extract location after explicit cue words.
        m = re.search(r"(?:在|地点|地址)\s*([^，。,\\s]{2,20})", text)
        if not m:
            return None
        return m.group(1).strip()

    def _regex_extract_requirement(text: str) -> Dict[str, Any]:
        # Lightweight rule-based requirement extraction.
        # Minimal extractor; replace with LLM + structured extraction later
        people = _extract_people(text)
        budget_yuan = _extract_budget_yuan(text)
        date_time = _extract_date_time(text)
        location = _extract_location(text)

        out: Dict[str, Any] = {"notes": text}
        if people is not None:
            out["people"] = people
        if budget_yuan is not None:
            out["budget_cny"] = budget_yuan * 100
        if date_time is not None:
            out["date_time"] = date_time
        if location is not None:
            out["location"] = location
        return out

    def _llm_extract_requirement(text: str) -> Optional[Dict[str, Any]]:
        # LLM-based extraction using structured outputs.
        if not settings.enable_llm_extract or llm_registry is None:
            return None
        llm = llm_registry.get_llm("ReceptionAgent")
        schema = {
            "type": "object",
            "properties": {
                "people": {"type": ["integer", "null"], "minimum": 1},
                "budget_cny": {
                    "type": ["integer", "null"],
                    "minimum": 0,
                    "description": "budget in fen",
                },
                "date_time": {"type": ["string", "null"]},
                "location": {"type": ["string", "null"]},
                "notes": {"type": ["string", "null"]},
            },
            "required": ["people", "budget_cny", "date_time", "location", "notes"],
            "additionalProperties": False,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "从用户文本中抽取人数、预算（分）、时间、地点。"
                    "返回JSON，字段仅限people/budget_cny/date_time/location/notes。"
                    "没有的信息请返回null。"
                ),
            },
            {"role": "user", "content": text},
        ]
        try:
            raw = llm.chat(
                messages,
                temperature=0,
                text_format={
                    "type": "json_schema",
                    "name": "requirement_extract",
                    "strict": True,
                    "schema": schema,
                },
            )
            data = json.loads(raw)
        except Exception as exc:
            logger.exception("LLM extract_requirement failed: %s", exc)
            return None
        if not isinstance(data, dict):
            return None
        data["notes"] = text
        return data

    def extract_requirement(text: str) -> Dict[str, Any]:
        # LLM-first extraction; fallback to regex for any missing fields.
        out: Dict[str, Any] = {}
        llm_out = _llm_extract_requirement(text)
        if isinstance(llm_out, dict):
            out.update({k: v for k, v in llm_out.items() if v not in (None, "")})
        if not out:
            out = _regex_extract_requirement(text)
        else:
            missing = [k for k in ("people", "budget_cny", "date_time", "location") if k not in out]
            if missing:
                regex_out = _regex_extract_requirement(text)
                for key in missing:
                    if key in regex_out and regex_out[key] not in (None, ""):
                        out[key] = regex_out[key]
                if "notes" not in out:
                    out["notes"] = regex_out.get("notes", text)

        # Treat messages with no usable requirement fields as "no-info" for intake loop.
        has_req = any(
            k in out and out[k] not in (None, "")
            for k in ("people", "budget_cny", "date_time", "location")
        )
        if not has_req:
            return {"ok": False, "reason": "no_requirements", "notes": text}
        return out

    def check_availability(chef_id: str, date_time: str) -> Dict[str, Any]:
        # Check chef availability for a given time.
        chef = repo.get_chef(chef_id)
        ok = bool(chef and chef.availability.get(date_time, True))
        return {"available": ok, "chef_id": chef_id, "date_time": date_time}

    def make_offer(
        lead_id: str,
        chef_id: Optional[str],
        price_cny: int,
        deposit_cny: int,
        items: List[str],
        breakdown: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        # Create and persist an offer.
        offer = Offer(
            offer_id=new_id("offer"),
            lead_id=lead_id,
            chef_id=chef_id,
            price_cny=price_cny,
            deposit_cny=deposit_cny,
            breakdown=breakdown or {},
            items=items,
        )
        repo.create_offer(offer)
        return offer.model_dump()

    def create_booking(lead_id: str, offer_id: str, hold_minutes: Optional[int] = None) -> Dict[str, Any]:
        # Create a booking with a hold window and link to lead.
        if hold_minutes is None:
            hold_minutes = settings.booking_hold_minutes
        booking = Booking(
            booking_id=new_id("book"),
            lead_id=lead_id,
            offer_id=offer_id,
            status="HOLD",
            hold_until=datetime.utcnow() + timedelta(minutes=hold_minutes),
        )
        repo.create_booking(booking)
        lead = repo.get_lead(lead_id)
        if lead:
            lead.last_booking_id = booking.booking_id
            repo.update_lead(lead)
        return booking.model_dump()

    def create_payment_link(booking_id: str, amount_cny: int) -> Dict[str, Any]:
        # Mock payment link generator.
        return {"booking_id": booking_id, "pay_url": f"https://pay.mock/{booking_id}?amt={amount_cny}"}

    def confirm_deposit(booking_id: str) -> Dict[str, Any]:
        # Mark deposit as paid for a booking.
        booking = repo.get_booking(booking_id)
        if not booking:
            raise ValueError("booking_not_found")
        booking.status = "DEPOSIT_PAID"
        booking.deposit_paid_at = datetime.utcnow()
        repo.update_booking(booking)
        return booking.model_dump()

    return {
        "extract_requirement": extract_requirement,
        "check_availability": check_availability,
        "make_offer": make_offer,
        "create_booking": create_booking,
        "create_payment_link": create_payment_link,
        "confirm_deposit": confirm_deposit,
    }
