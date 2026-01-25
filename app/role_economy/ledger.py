from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class LedgerEntry(BaseModel):
    entry_id: str
    booking_id: str
    amount_cny: int
    memo: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Ledger(BaseModel):
    entries: List[LedgerEntry] = Field(default_factory=list)

    def add(self, e: LedgerEntry) -> None:
        self.entries.append(e)
