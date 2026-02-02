from __future__ import annotations
from typing import Dict, Any, Optional
import json
import re
from app.aim.agent_base import BaseAgent, AgentContext
from app.aim.llm.composer import compose_reply
from app.aim.llm.registry import LLMRegistry
from app.config import settings
from app.storage.base import Repo
from app.domains.private_chef.state_machine import (
    apply_requirement_update,
    advance_lead,
    is_min_info_ready,
    missing_requirements,
)
from app.domains.private_chef import proposal_engine

_PLAN_KEYWORDS = {
    "basic": ["基础", "入门"],
    "standard": ["标准", "经典", "推荐"],
    "premium": ["升级", "高级", "豪华"],
}
_CN_NUM = {"一": 1, "二": 2, "三": 3}

def _rule_select_plan(text: str, plans: list[dict]) -> Optional[dict]:
    # Deterministic selection parsing (no LLM).
    t = text.strip()
    if not t:
        return None

    # Explicit numeric choice.
    if re.fullmatch(r"[1-3]", t):
        idx = int(t) - 1
        return plans[idx] if 0 <= idx < len(plans) else None

    m = re.search(r"(?:选|要|就|方案|档|号)\s*([1-3])", t)
    if not m:
        m = re.search(r"([1-3])\s*(?:号|档|款|方案)", t)
    if m:
        idx = int(m.group(1)) - 1
        return plans[idx] if 0 <= idx < len(plans) else None

    # Chinese numerals with explicit context.
    m_cn = re.search(r"(?:选|要|就|方案|档|号)\s*(一|二|三)(?:号|档|款|方案)?", t)
    if not m_cn:
        m_cn = re.search(r"第(一|二|三)(?:号|档|款|方案)", t)
    if m_cn:
        v = _CN_NUM.get(m_cn.group(1))
        if v:
            idx = v - 1
            return plans[idx] if 0 <= idx < len(plans) else None

    # Plan name keywords.
    for plan in plans:
        keywords = _PLAN_KEYWORDS.get(plan["plan_id"], [])
        if any(k in t for k in keywords):
            return plan
    return None

def _format_plans(plans: list[dict]) -> str:
    lines = []
    for idx, p in enumerate(plans, start=1):
        highlights = "，".join(p.get("highlights", []))
        lines.append(
            f"{idx}. {p['name']} ¥{p['price_cny']/100:.0f}"
            f"（{highlights}，定金¥{p['deposit_cny']/100:.0f}）"
        )
    return "\n".join(lines)

def _should_try_llm(text: str) -> bool:
    cues = ["方案", "档", "选", "基础", "标准", "升级", "推荐"]
    return any(c in text for c in cues) or len(text.strip()) <= 8


class ProposalAgent(BaseAgent):
    # Proposal agent that drives a closable offer.
    name = "ProposalAgent"

    def __init__(self, repo: Repo, llm_registry: LLMRegistry | None = None):
        # Repo used for lead/chef lookup.
        self.repo = repo
        self.llm_registry = llm_registry

    def _llm_select_plan(self, text: str, plans: list[dict]) -> Optional[dict]:
        if not settings.enable_llm_extract or self.llm_registry is None:
            return None
        plan_ids = [p["plan_id"] for p in plans]
        llm = self.llm_registry.get_llm(self.name)
        schema = {
            "type": "object",
            "properties": {
                "choice": {"type": ["string", "null"]},
            },
            "required": ["choice"],
            "additionalProperties": False,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "判断用户选择的方案档位：basic/standard/premium。"
                    "基础=basic，标准=standard，升级=premium。"
                    "如果不确定或未选择，返回 null。"
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
                    "name": "plan_choice",
                    "strict": True,
                    "schema": schema,
                },
            )
            data = json.loads(raw)
        except Exception:
            return None
        choice = data.get("choice")
        if choice in plan_ids:
            return next(p for p in plans if p["plan_id"] == choice)
        return None

    def run(self, ctx: AgentContext, input_text: str, tools, **kwargs) -> Dict[str, Any]:
        # Generate proposal options and close after user selects a plan.
        lead = self.repo.get_active_lead(ctx.user_id)
        if not lead:
            return {"reply": "我还没获取到你的需求信息，可以简单说下人数/时间/预算吗？"}

        extracted = tools.call("extract_requirement", ctx=ctx, text=input_text)
        if isinstance(extracted, dict) and extracted.get("ok") is False:
            # If we already have minimum info, allow non-informational replies.
            if not is_min_info_ready(lead.req):
                return {"reply": "我这边没能识别到关键信息，能补充一下用餐时间、人数、地点和预算吗？", "lead": lead.model_dump()}
            extracted = {}

        if isinstance(extracted, dict) and extracted:
            apply_requirement_update(lead, extracted)
            lead = advance_lead(lead, "INFO_UPDATED")

        if not is_min_info_ready(lead.req):
            missing = missing_requirements(lead.req)
            reply = "为了给你更准确的方案，还需要：" + "、".join(missing) + "。"
            self.repo.update_lead(lead)
            return {"reply": reply, "lead": lead.model_dump()}

        offer_obj = self.repo.get_offer_by_lead(lead.lead_id)
        offer: Dict[str, Any] | None = offer_obj.model_dump() if offer_obj else None

        selected_name = None
        if not offer:
            plans = proposal_engine.build_proposals(lead)
            selected = _rule_select_plan(input_text, plans)
            if not selected:
                if _should_try_llm(input_text):
                    selected = self._llm_select_plan(input_text, plans)
            if not selected:
                plan_text = _format_plans(plans)
                reply = (
                    "我给你准备了三档方案，便于比较：\n"
                    f"{plan_text}\n"
                    "回复 1/2/3 或 方案名即可选定。"
                )
                reply = compose_reply(
                    self.llm_registry,
                    self.name,
                    input_text,
                    {"lead": lead.model_dump(), "plans": plans},
                    reply,
                )
                self.repo.update_lead(lead)
                return {"reply": reply, "plans": plans, "lead": lead.model_dump()}

            selected_name = selected.get("name")
            offer = tools.call(
                "make_offer",
                ctx=ctx,
                lead_id=lead.lead_id,
                chef_id=None,
                price_cny=selected["price_cny"],
                deposit_cny=selected["deposit_cny"],
                items=selected.get("items", []),
                breakdown=selected.get("breakdown"),
            )
            if isinstance(offer, dict) and offer.get("ok") is False:
                return {"reply": "我这边生成方案时出了点问题，稍等我再试一下。"}
            lead.last_offer_id = offer.get("offer_id")
            lead = advance_lead(lead, "OFFER_CREATED")

        booking_obj = None
        booking_list = self.repo.list_bookings_by_lead(lead.lead_id)
        if booking_list:
            booking_obj = booking_list[0]
        booking: Dict[str, Any] | None = booking_obj.model_dump() if booking_obj else None

        if not booking or booking.get("offer_id") != offer["offer_id"]:
            booking = tools.call(
                "create_booking",
                ctx=ctx,
                lead_id=lead.lead_id,
                offer_id=offer["offer_id"],
            )
            if isinstance(booking, dict) and booking.get("ok") is False:
                return {"reply": "我这边创建锁档时出了点问题，稍等我再试一下。"}
            lead.last_booking_id = booking.get("booking_id")
            lead = advance_lead(lead, "BOOKING_CREATED")

        self.repo.update_lead(lead)

        payment = tools.call(
            "create_payment_link",
            ctx=ctx,
            booking_id=booking["booking_id"],
            amount_cny=offer["deposit_cny"],
        )
        if isinstance(payment, dict) and payment.get("ok") is False:
            payment = {"pay_url": "支付链接生成失败，请稍等我重新发送。"}

        hold_until = booking.get("hold_until")
        hold_text = str(hold_until) if hold_until else "稍后"
        chef_line = "具体厨师将在确认后为你匹配。"
        title = f"已为你确认【{selected_name}】方案。" if selected_name else "方案已为你确认。"
        reply = (
            f"{title}"
            f"参考价 ¥{offer['price_cny']/100:.0f}，定金 ¥{offer['deposit_cny']/100:.0f}。"
            f"{chef_line}"
            f"我先为你锁档到 {hold_text}，支付定金即可确认：{payment.get('pay_url')}。"
        )
        reply = compose_reply(
            self.llm_registry,
            self.name,
            input_text,
            {"lead": lead.model_dump(), "offer": offer, "booking": booking, "payment": payment},
            reply,
        )
        return {"reply": reply, "offer": offer, "booking": booking, "lead": lead.model_dump(), "payment": payment}
