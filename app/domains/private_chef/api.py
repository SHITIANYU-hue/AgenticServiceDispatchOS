from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.storage.base import Repo
from app.storage.models import User, Lead, ConversationMessage, LeadStage
from app.core.ids import new_id
from app.aim.agent_base import AgentContext
from app.aim.workflow import route_agent, agent_role
from app.aim.guardrails import should_escalate
from app.aim.runtime import AgentRuntime
from app.domains.private_chef.state_machine import is_intake_confirmed

router = APIRouter(prefix="/private_chef", tags=["private_chef"])

class InMsg(BaseModel):
    # Incoming message payload.
    channel: str
    external_id: str
    source: str = "unknown"
    text: str

def get_repo(request: Request) -> Repo:
    # Resolve repo from app state.
    return request.app.state.repo

def get_runtime(request: Request) -> AgentRuntime:
    # Resolve runtime from app state.
    return request.app.state.runtime

def ensure_user_and_lead(repo: Repo, channel: str, external_id: str, source: str):
    # Create or reuse user and active lead.
    u = repo.get_user_by_external(channel, external_id)
    if not u:
        u = User(user_id=new_id("u"), channel=channel, external_id=external_id)
        repo.upsert_user(u)

    lead = repo.get_active_lead(u.user_id)
    if not lead:
        lead = Lead(lead_id=new_id("lead"), user_id=u.user_id, source=source)
        repo.create_lead(lead)
    return u, lead

@router.post("/message")
def on_message(payload: InMsg, repo: Repo = Depends(get_repo), rt: AgentRuntime = Depends(get_runtime)):
    # Main chat endpoint: guardrails, routing, agent step, logging.
    u, lead = ensure_user_and_lead(repo, payload.channel, payload.external_id, payload.source)

    repo.add_message(ConversationMessage(
        msg_id=new_id("m"),
        user_id=u.user_id,
        lead_id=lead.lead_id,
        role="user",
        text=payload.text
    ))

    flag, reason, action = should_escalate(payload.text)
    if action == "ESCALATE":
        reply = f"我理解你的诉求。这个情况我先帮你转人工同事跟进（原因：{reason}）。"
        repo.add_message(ConversationMessage(
            msg_id=new_id("m"),
            user_id=u.user_id,
            lead_id=lead.lead_id,
            role="agent",
            text=reply
        ))
        return {"reply": reply, "escalated": True, "reason": reason, "action": action, "lead": lead.model_dump()}
    if action == "HARD_REFUSE":
        reply = "为了保障双方权益，平台外的私下交易/联系我无法协助。我们可以继续在平台内沟通。"
        repo.add_message(ConversationMessage(
            msg_id=new_id("m"),
            user_id=u.user_id,
            lead_id=lead.lead_id,
            role="agent",
            text=reply
        ))
        return {"reply": reply, "escalated": False, "reason": reason, "action": action, "lead": lead.model_dump()}
    if action == "SOFT_REFUSE":
        reply = "我理解你的期待，但我不能做出超出平台规则的保证。我们可以根据规则提供可行方案。"
        repo.add_message(ConversationMessage(
            msg_id=new_id("m"),
            user_id=u.user_id,
            lead_id=lead.lead_id,
            role="agent",
            text=reply
        ))
        return {"reply": reply, "escalated": False, "reason": reason, "action": action, "lead": lead.model_dump()}

    ctx = AgentContext(user_id=u.user_id, lead_id=lead.lead_id, role="UserProxy")
    agent_name, route_reason = route_agent(lead, payload.text, repo)
    ctx.role = agent_role(agent_name)
    out = rt.step(agent_name, ctx, payload.text)
    out["agent_name"] = agent_name
    out["route_reason"] = route_reason

    agent_outputs = [out]

    if agent_name == "ReceptionAgent":
        lead = repo.get_active_lead(u.user_id) or lead
        if out.get("ready_for_proposal") and is_intake_confirmed(lead.req):
            ctx.role = agent_role("ProposalAgent")
            out = rt.step("ProposalAgent", ctx, payload.text)
            out["agent_name"] = "ProposalAgent"
            out["route_reason"] = "auto_after_reception"
            agent_outputs.append(out)

    for item in agent_outputs:
        repo.add_message(ConversationMessage(
            msg_id=new_id("m"),
            user_id=u.user_id,
            lead_id=lead.lead_id,
            role="agent",
            text=item.get("reply", "")
        ))
    if len(agent_outputs) == 2:
        combined = "\n".join(
            [agent_outputs[0].get("reply", ""), agent_outputs[1].get("reply", "")]
        ).strip()
        agent_outputs[-1]["reply"] = combined
        agent_outputs[-1]["agent_chain"] = ["ReceptionAgent", "ProposalAgent"]
    return agent_outputs[-1]

@router.get("/health")
def health():
    # Lightweight health check.
    return {"ok": True}
