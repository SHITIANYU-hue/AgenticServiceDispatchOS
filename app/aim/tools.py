from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Any

@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[..., Any]

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def call(self, name: str, **kwargs) -> Any:
        if name not in self.tools:
            raise ValueError(f"Tool not found: {name}")
        return self.tools[name].fn(**kwargs)

    def list(self) -> list[str]:
        return list(self.tools.keys())
