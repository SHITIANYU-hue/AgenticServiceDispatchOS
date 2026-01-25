from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.storage.base import Repo
from app.storage.models import User, Lead, ConversationMessage, LeadStage
from app.core.ids import new_id
from app.aim.agent_base import AgentContext
from app.aim.workflow import route_agent
from app.aim.guardrails import should_escalate
from app.aim.runtime import AgentRuntime

router = APIRouter(prefix="/private_chef", tags=["private_chef"])

class InMsg(BaseModel):
    channel: str
    external_id: str
    source: str = "unknown"
    text: str

def get_repo(request: Request) -> Repo:
    return request.app.state.repo

def get_runtime(request: Request) -> AgentRuntime:
    return request.app.state.runtime

def ensure_user_and_lead(repo: Repo, channel: str, external_id: str, source: str):
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
    u, lead = ensure_user_and_lead(repo, payload.channel, payload.external_id, payload.source)

    repo.add_message(ConversationMessage(
        msg_id=new_id("m"),
        user_id=u.user_id,
        lead_id=lead.lead_id,
        role="user",
        text=payload.text
    ))

    esc, reason = should_escalate(payload.text)
    if esc:
        reply = f"我理解你的诉求。这个情况我先帮你转人工同事跟进（原因：{reason}）。"
        repo.add_message(ConversationMessage(
            msg_id=new_id("m"),
            user_id=u.user_id,
            lead_id=lead.lead_id,
            role="agent",
            text=reply
        ))
        return {"reply": reply, "escalated": True, "reason": reason, "lead": lead.model_dump()}

    ctx = AgentContext(user_id=u.user_id, lead_id=lead.lead_id, role="UserProxy")
    agent_name = route_agent(lead.stage)
    out = rt.step(agent_name, ctx, payload.text)

    repo.add_message(ConversationMessage(
        msg_id=new_id("m"),
        user_id=u.user_id,
        lead_id=lead.lead_id,
        role="agent",
        text=out.get("reply", "")
    ))
    return out

@router.get("/health")
def health():
    return {"ok": True}
