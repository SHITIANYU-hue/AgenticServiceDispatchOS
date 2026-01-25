from __future__ import annotations
from fastapi import FastAPI
from app.core.logging import setup_logging
from app.storage.memory import InMemoryRepo
from app.storage.models import Chef
from app.aim.tools import ToolRegistry, Tool
from app.aim.runtime import AgentRuntime
from app.domains.private_chef.tools import build_tools
from app.domains.private_chef.agents.reception import ReceptionAgent
from app.domains.private_chef.agents.dispatch import DispatchAgent
from app.domains.private_chef.api import router as private_chef_router

setup_logging()

app = FastAPI(title="Agentic Service Dispatch OS")

# ---- singletons (later swap to DI container) ----
repo = InMemoryRepo()

# Seed example chefs
repo.chefs["chef_1"] = Chef(
    chef_id="chef_1",
    name="Chef Li",
    cuisines=["川菜", "粤菜"],
    base_price_cny=30000,  # ¥300
    service_radius_km=20,
    max_people=12,
    availability={}
)
repo.chefs["chef_2"] = Chef(
    chef_id="chef_2",
    name="Chef Wang",
    cuisines=["法餐", "融合"],
    base_price_cny=60000,  # ¥600
    service_radius_km=15,
    max_people=8,
    availability={}
)

tools = ToolRegistry()
for name, fn in build_tools(repo).items():
    tools.register(Tool(name=name, description=name, fn=fn))

runtime = AgentRuntime(tools)
runtime.register_agent(ReceptionAgent(repo))
runtime.register_agent(DispatchAgent(repo))

# Attach to app state for dependency injection
app.state.repo = repo
app.state.runtime = runtime
app.state.tools = tools

app.include_router(private_chef_router)

@app.get("/")
def root():
    return {"app": "agent-dispatch-os", "tools": tools.list(), "agents": list(runtime.agents.keys())}
