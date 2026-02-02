from __future__ import annotations
import os

from app.aim.agent_base import AgentContext
from app.aim.guardrails import should_escalate
from app.aim.runtime import AgentRuntime
from app.aim.tools import ToolRegistry, Tool
from app.aim.workflow import route_agent, agent_role
from app.aim.llm.registry import build_llm_registry
from app.config import settings
from app.core.ids import new_id
from app.domains.private_chef.agents.dispatch import DispatchAgent
from app.domains.private_chef.agents.negotiation import NegotiationAgent
from app.domains.private_chef.agents.ops import OpsAgent
from app.domains.private_chef.agents.proposal import ProposalAgent
from app.domains.private_chef.agents.reception import ReceptionAgent
from app.domains.private_chef.tools import build_tools
from app.domains.private_chef.state_machine import is_intake_confirmed
from app.storage.memory import InMemoryRepo
from app.storage.models import Chef, ConversationMessage, Lead, User


def seed_chefs(repo: InMemoryRepo) -> None:
    # Minimal seed data for local debug.
    repo.chefs["chef_1"] = Chef(
        chef_id="chef_1",
        name="Chef Li",
        cuisines=["川菜", "粤菜"],
        base_price_cny=30000,  # ¥300
        service_radius_km=20,
        max_people=12,
        availability={},
    )
    repo.chefs["chef_2"] = Chef(
        chef_id="chef_2",
        name="Chef Wang",
        cuisines=["法餐", "融合"],
        base_price_cny=60000,  # ¥600
        service_radius_km=15,
        max_people=8,
        availability={},
    )


def ensure_user_and_lead(repo: InMemoryRepo, channel: str, external_id: str, source: str) -> tuple[User, Lead]:
    # Create or reuse user and active lead for a local chat session.
    u = repo.get_user_by_external(channel, external_id)
    if not u:
        u = User(user_id=new_id("u"), channel=channel, external_id=external_id)
        repo.upsert_user(u)
    lead = repo.get_active_lead(u.user_id)
    if not lead:
        lead = Lead(lead_id=new_id("lead"), user_id=u.user_id, source=source)
        repo.create_lead(lead)
    return u, lead


def build_runtime(repo: InMemoryRepo) -> tuple[AgentRuntime, ToolRegistry]:
    tools = ToolRegistry(repo)
    enable_any_llm = settings.enable_llm or settings.enable_llm_extract or os.environ.get("ENABLE_LLM") in ("1", "true", "TRUE", "True")
    llm_registry = build_llm_registry() if enable_any_llm else None
    for name, fn in build_tools(repo, llm_registry).items():
        tools.register(Tool(name=name, description=name, fn=fn))

    runtime = AgentRuntime(tools)
    runtime.register_agent(ReceptionAgent(repo, llm_registry))
    runtime.register_agent(DispatchAgent(repo, llm_registry))
    runtime.register_agent(NegotiationAgent(repo, llm_registry))
    runtime.register_agent(OpsAgent(repo))
    runtime.register_agent(ProposalAgent(repo, llm_registry))
    return runtime, tools


def main() -> None:
    repo = InMemoryRepo()
    seed_chefs(repo)
    runtime, _tools = build_runtime(repo)

    u, lead = ensure_user_and_lead(repo, channel="local", external_id="debug", source="cli")
    ctx = AgentContext(user_id=u.user_id, lead_id=lead.lead_id, role="UserProxy")

    print("Local chat started. Type 'exit' to quit.")
    # Trigger a welcome message immediately on session start.
    ctx.role = agent_role("ReceptionAgent")
    out = runtime.step("ReceptionAgent", ctx, "")
    welcome = out.get("reply", "")
    if welcome:
        repo.add_message(ConversationMessage(
            msg_id=new_id("m"),
            user_id=u.user_id,
            lead_id=lead.lead_id,
            role="agent",
            text=welcome,
        ))
        print(f"assistant[ReceptionAgent]> {welcome}")

    while True:
        text = input("user> ").strip()
        if not text:
            continue
        if text.lower() in ("exit", "quit", "q"):
            break

        repo.add_message(ConversationMessage(
            msg_id=new_id("m"),
            user_id=u.user_id,
            lead_id=lead.lead_id,
            role="user",
            text=text,
        ))

        flag, reason, action = should_escalate(text)
        agent_label = "System"
        if action != "OK":
            if action == "ESCALATE":
                reply = f"我理解你的诉求。这个情况我先帮你转人工同事跟进（原因：{reason}）。"
            elif action == "HARD_REFUSE":
                reply = "为了保障双方权益，平台外的私下交易/联系我无法协助。我们可以继续在平台内沟通。"
            else:
                reply = "我理解你的期待，但我不能做出超出平台规则的保证。我们可以根据规则提供可行方案。"
        else:
            lead = repo.get_active_lead(u.user_id) or lead
            agent_name, route_reason = route_agent(lead, text, repo)
            ctx.role = agent_role(agent_name)
            out = runtime.step(agent_name, ctx, text)
            out["route_reason"] = route_reason
            agent_outputs = [out]

            if agent_name == "ReceptionAgent":
                lead = repo.get_active_lead(u.user_id) or lead
                # Only auto-handoff after explicit intake confirmation.
                if out.get("ready_for_proposal") and is_intake_confirmed(lead.req):
                    ctx.role = agent_role("ProposalAgent")
                    out = runtime.step("ProposalAgent", ctx, text)
                    out["route_reason"] = "auto_after_reception"
                    agent_outputs.append(out)

            for item in agent_outputs:
                repo.add_message(ConversationMessage(
                    msg_id=new_id("m"),
                    user_id=u.user_id,
                    lead_id=lead.lead_id,
                    role="agent",
                    text=item.get("reply", ""),
                ))
            if len(agent_outputs) == 2:
                combined = "\n".join(
                    [agent_outputs[0].get("reply", ""), agent_outputs[1].get("reply", "")]
                ).strip()
                reply = combined
                agent_label = "ReceptionAgent→ProposalAgent"
            else:
                reply = agent_outputs[-1].get("reply", "")
                agent_label = agent_name

        if action != "OK":
            repo.add_message(ConversationMessage(
                msg_id=new_id("m"),
                user_id=u.user_id,
                lead_id=lead.lead_id,
                role="agent",
                text=reply,
            ))
        print(f"assistant[{agent_label}]> {reply}")


if __name__ == "__main__":
    main()
