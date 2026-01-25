from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LLM(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        ...
