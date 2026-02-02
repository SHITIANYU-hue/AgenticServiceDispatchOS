from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Any

from app.aim.agent_base import AgentContext
from app.role_economy.roles import ROLE_USER_PROXY, ROLE_PLATFORM_SALES, ROLE_MERCHANT_SERVICE
from app.storage.base import Repo

@dataclass
class Tool:
    # Tool metadata wrapper for registry.
    name: str
    description: str
    fn: Callable[..., Any]

class ToolRegistry:
    # Registry with permission checks and call logging.
    def __init__(self, repo: Repo):
        # Keep repo for logging.
        self.repo = repo
        self.tools: Dict[str, Tool] = {}
        self._role_allow_tools = {
            ROLE_USER_PROXY.role_name: set(ROLE_USER_PROXY.permission.allow_tools),
            ROLE_PLATFORM_SALES.role_name: set(ROLE_PLATFORM_SALES.permission.allow_tools),
            ROLE_MERCHANT_SERVICE.role_name: set(ROLE_MERCHANT_SERVICE.permission.allow_tools),
        }

    def register(self, tool: Tool) -> None:
        # Add/replace a tool entry.
        self.tools[tool.name] = tool

    def _is_allowed(self, role: str, tool_name: str) -> bool:
        # Role-based allow-list check.
        allow_tools = self._role_allow_tools.get(role)
        if allow_tools is None:
            return False
        return tool_name in allow_tools

    def _summarize_result(self, result: Any) -> str:
        # Compact result for logging.
        summary = str(result)
        return summary[:200]

    def _log_call(self, ctx: AgentContext, tool_name: str, args: Dict[str, Any], result_summary: str) -> None:
        # Append tool call log to repo if available.
        if not hasattr(self.repo, "tool_call_logs"):
            return
        self.repo.tool_call_logs.append({
            "ts": datetime.utcnow(),
            "lead_id": ctx.lead_id,
            "tool_name": tool_name,
            "args": args,
            "result_summary": result_summary,
        })

    def call(self, name: str, ctx: AgentContext, **kwargs) -> Any:
        # Validate permission, invoke tool, and log outcome.
        if name not in self.tools:
            error = {"ok": False, "error": {"type": "tool_not_found", "message": f"Tool not found: {name}"}}
            self._log_call(ctx, name, kwargs, "tool_not_found")
            return error

        if not self._is_allowed(ctx.role, name):
            error = {"ok": False, "error": {"type": "permission_denied", "message": f"Role {ctx.role} cannot call {name}"}}
            self._log_call(ctx, name, kwargs, "permission_denied")
            return error

        try:
            result = self.tools[name].fn(**kwargs)
            self._log_call(ctx, name, kwargs, self._summarize_result(result))
            return result
        except Exception as exc:
            error = {"ok": False, "error": {"type": "tool_error", "message": str(exc)}}
            self._log_call(ctx, name, kwargs, f"tool_error: {exc}")
            return error

    def list(self) -> list[str]:
        # Return tool names for inspection.
        return list(self.tools.keys())
