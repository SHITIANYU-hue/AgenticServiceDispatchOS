from __future__ import annotations
"""
ReceptionAgent workflow:
- Call tools.extract_requirement to parse user input.
- Update lead requirement card and preserve partial info.
- Ask for missing info (max 2 questions per reply).
- Ask for final confirmation before proposal.
"""
from typing import Dict, Any
from app.aim.agent_base import BaseAgent, AgentContext
from app.aim.llm.composer import compose_reply
from app.aim.llm.registry import LLMRegistry
from app.storage.base import Repo
from app.storage.models import LeadStage
from app.domains.private_chef.state_machine import (
    apply_requirement_update,
    advance_lead,
    is_min_info_ready,
    missing_requirements,
)

class ReceptionAgent(BaseAgent):
    """Intake agent that gathers requirements and confirms them before proposal."""
    # Track the core intake fields for confirmation invalidation.
    name = "ReceptionAgent"
    _REQ_FIELDS = ("date_time", "people", "location", "budget_cny")
    # Keywords that make user free-text notes worth surfacing in summary.
    _NOTE_HINTS = (
        "忌口", "过敏", "不吃", "口味", "清淡", "辣",
        "生日", "纪念日", "庆祝", "小孩", "孩子", "老人", "孕妇",
        "素", "海鲜", "牛肉", "羊肉", "猪肉", "坚果",
    )

    def __init__(self, repo: Repo, llm_registry: LLMRegistry | None = None):
        # Repo used for lead persistence.
        self.repo = repo
        self.llm_registry = llm_registry

    def _is_confirmation(self, text: str) -> bool:
        """Heuristic check for a short, affirmative confirmation reply."""
        t = text.strip().lower()
        if not t:
            return False
        if "?" in t or "？" in t or "吗" in t:
            return False
        exact = {
            "好", "好的", "行", "可以", "可以的", "ok", "okay",
            "确认", "没问题", "没错", "对", "对的", "是", "是的",
            "就这样", "那就这样", "确定", "confirm",
        }
        if t in exact:
            return True
        if len(t) <= 8 and any(k in t for k in ("确认", "没问题", "没错", "就这样", "可以", "好的", "行", "ok", "okay")):
            return True
        return False

    def _is_negative(self, text: str) -> bool:
        """Heuristic check for a short, negative confirmation reply."""
        t = text.strip().lower()
        if not t:
            return False
        if "?" in t or "？" in t:
            return False
        negatives = ("不", "不是", "不对", "不行", "不可以", "不是的", "不行的", "否", "no")
        return any(k in t for k in negatives)

    def _should_include_notes(self, notes: str) -> bool:
        """Decide if notes should be included in the summary."""
        return any(k in notes for k in self._NOTE_HINTS)

    def _merge_notes(self, lead, notes: str) -> bool:
        """Append notes into lead.req.notes if they add new, non-confirmation info."""
        note = notes.strip()
        if not note or self._is_confirmation(note) or self._is_negative(note):
            return False
        if not lead.req.notes:
            lead.req.notes = note
            return True
        if note not in lead.req.notes:
            lead.req.notes = f"{lead.req.notes}；{note}"
            return True
        return False

    def _format_summary(self, req) -> str:
        """Build a compact summary of the currently known intake fields."""
        parts = []
        if req.date_time:
            parts.append(f"用餐时间 {req.date_time}")
        if req.people:
            parts.append(f"{req.people}人")
        if req.location:
            parts.append(f"地点 {req.location}")
        if req.budget_cny:
            parts.append(f"预算约 ¥{req.budget_cny/100:.0f}")
        if req.cuisine:
            parts.append(f"口味 {req.cuisine}")
        if req.allergies:
            parts.append(f"忌口 {req.allergies}")
        if req.notes and self._should_include_notes(req.notes):
            parts.append(f"备注 {req.notes}")
        return "，".join(parts)

    def _build_missing_reply(self, lead, input_text: str, was_new: bool, no_info: bool = False) -> str:
        """Ask for missing fields while optionally echoing known info."""
        missing = missing_requirements(lead.req)
        summary = self._format_summary(lead.req)
        if no_info and not summary:
            reply = "我这边没能识别到关键信息，能补充一下用餐时间、人数、地点和预算吗？"
        else:
            if summary:
                reply = "收到：" + summary + "。我还需要确认：" + "、".join(missing[:2]) + "。"
            else:
                reply = "收到～我还需要确认：" + "、".join(missing[:2]) + "。"
        reply = compose_reply(
            self.llm_registry,
            self.name,
            input_text,
            {"missing": missing[:2], "summary": summary, "lead": lead.model_dump()},
            reply,
        )
        if was_new:
            reply = "欢迎光临～" + reply
        return reply

    def _build_confirmation_prompt(self, lead, input_text: str, was_new: bool) -> str:
        """Ask the user to confirm the summarized intake before proposal."""
        summary = self._format_summary(lead.req)
        if summary:
            reply = f"请确认以下需求：{summary}。如需修改请告诉我。回复 是/否。"
        else:
            reply = "请确认用餐时间、人数、地点和预算是否正确？回复 是/否。"
        reply = compose_reply(
            self.llm_registry,
            self.name,
            input_text,
            {"summary": summary, "lead": lead.model_dump()},
            reply,
        )
        if was_new:
            reply = "欢迎光临～" + reply
        return reply

    def _build_confirmation_ack(self, lead, input_text: str, was_new: bool) -> str:
        """Acknowledgment after confirmation is received."""
        reply = "好的，信息已确认。我马上为你推荐方案。"
        reply = compose_reply(
            self.llm_registry,
            self.name,
            input_text,
            {"lead": lead.model_dump()},
            reply,
        )
        if was_new:
            reply = "欢迎光临～" + reply
        return reply

    def _build_restart_reply(self, lead, input_text: str, was_new: bool) -> str:
        """Ask the user to correct or re-provide intake details after a rejection."""
        summary = self._format_summary(lead.req)
        if summary:
            reply = f"好的，我们重新确认。当前记录：{summary}。请告诉我需要修改的内容。"
        else:
            reply = "好的，我们重新确认。请告诉我用餐时间、人数、地点和预算。"
        reply = compose_reply(
            self.llm_registry,
            self.name,
            input_text,
            {"summary": summary, "lead": lead.model_dump()},
            reply,
        )
        if was_new:
            reply = "欢迎光临～" + reply
        return reply

    def _handle_confirmation(self, lead, input_text: str, was_new: bool) -> Dict[str, Any]:
        """Confirmation state machine: prompt, detect, or acknowledge."""
        if lead.req.confirmed:
            reply = self._build_confirmation_ack(lead, input_text, was_new)
            return {"reply": reply, "lead": lead.model_dump(), "ready_for_proposal": True}
        if lead.req.confirmation_requested and self._is_negative(input_text):
            lead.req.confirmed = False
            lead.req.confirmation_requested = False
            self.repo.update_lead(lead)
            reply = self._build_restart_reply(lead, input_text, was_new)
            return {"reply": reply, "lead": lead.model_dump(), "ready_for_proposal": False}
        if lead.req.confirmation_requested and self._is_confirmation(input_text):
            lead.req.confirmed = True
            self.repo.update_lead(lead)
            reply = self._build_confirmation_ack(lead, input_text, was_new)
            return {"reply": reply, "lead": lead.model_dump(), "ready_for_proposal": True}
        lead.req.confirmation_requested = True
        self.repo.update_lead(lead)
        reply = self._build_confirmation_prompt(lead, input_text, was_new)
        return {"reply": reply, "lead": lead.model_dump(), "ready_for_proposal": False}

    def run(self, ctx: AgentContext, input_text: str, tools, **kwargs) -> Dict[str, Any]:
        """Extract requirements, persist partial info, and confirm before proposal."""
        # Flow:
        # 1) Call extractor tool to parse requirements from user text.
        # 2) Merge into lead, advance stage if ready.
        # 3) Ask for missing fields (max 2 items per reply).
        lead = self.repo.get_active_lead(ctx.user_id)
        if not lead:
            return {"reply": "我还没获取到你的需求信息，可以简单说下用餐时间、人数、地点和预算吗？"}
        was_new = bool(lead.stage == LeadStage.NEW)
        extracted = tools.call("extract_requirement", ctx=ctx, text=input_text)
        if not isinstance(extracted, dict):
            extracted = {"ok": False, "reason": "invalid_extract", "notes": input_text}

        if extracted.get("ok") is False:
            if was_new and not input_text.strip():
                reply = "欢迎光临～请告诉我用餐时间、人数、地点和预算吗？"
                lead.stage = LeadStage.INFO_GATHERING
                self.repo.update_lead(lead)
                return {"reply": reply, "lead": lead.model_dump()}

            notes_updated = False
            if isinstance(extracted.get("notes"), str):
                notes_updated = self._merge_notes(lead, extracted["notes"])
            if lead.stage == LeadStage.NEW:
                lead.stage = LeadStage.INFO_GATHERING
            if notes_updated or was_new:
                self.repo.update_lead(lead)

            if is_min_info_ready(lead.req):
                # Minimum info is ready; move into explicit confirmation step.
                return self._handle_confirmation(lead, input_text, was_new)

            reply = self._build_missing_reply(lead, input_text, was_new, no_info=True)
            return {"reply": reply, "lead": lead.model_dump()}

        before = {k: getattr(lead.req, k) for k in self._REQ_FIELDS}
        update_payload = {k: v for k, v in extracted.items() if k != "notes"}
        apply_requirement_update(lead, update_payload)
        if isinstance(extracted.get("notes"), str):
            self._merge_notes(lead, extracted["notes"])

        if any(before[k] != getattr(lead.req, k) for k in self._REQ_FIELDS):
            # Any core field change invalidates prior confirmation.
            lead.req.confirmed = False
            lead.req.confirmation_requested = False

        lead = advance_lead(lead, "INFO_UPDATED")
        if lead.stage == LeadStage.NEW:
            lead.stage = LeadStage.INFO_GATHERING
        self.repo.update_lead(lead)

        if not is_min_info_ready(lead.req):
            reply = self._build_missing_reply(lead, input_text, was_new)
            return {"reply": reply, "lead": lead.model_dump()}

        return self._handle_confirmation(lead, input_text, was_new)
