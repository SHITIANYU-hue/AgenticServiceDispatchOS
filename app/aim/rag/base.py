from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict

class RAG(ABC):
    @abstractmethod
    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        ...
