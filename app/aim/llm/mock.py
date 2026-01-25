from __future__ import annotations
from typing import Dict, Any, List
from .base import LLM

class MockLLM(LLM):
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # Very naive echo-style mock.
        last = messages[-1]["content"] if messages else ""
        return f"(mock) 收到：{last}"
