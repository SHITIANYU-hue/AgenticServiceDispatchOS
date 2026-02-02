# Agentic Service Dispatch OS

An opinionated, runnable **Agentic Service Dispatch OS** for high‑consultation services
(private chefs, photographers, trainers, etc.). It models the *transaction flow* instead of
just chat, and splits responsibilities across agents with explicit state transitions.

## What This Project Does

- **AIM layer**: agent runtime, tools, guardrails, routing, LLM profiles
- **Role economy**: role‑based tool permissions (minimal but enforced)
- **Domain**: `private_chef` end‑to‑end flow (lead → offer → booking → payment → dispatch)
- **Storage**: in‑memory repo (easy to swap to DB later)

## Current Flow (private_chef)

1) **ReceptionAgent**: intake & requirement completion  
2) **ProposalAgent**: generates *proposal tiers* → user chooses → creates Offer/Booking/Pay link  
3) **NegotiationAgent** (optional): price bargaining with floor protection  
4) **OpsAgent**: confirms deposit & handles cancel/refund/reschedule policy  
5) **DispatchAgent**: assigns a real chef *after deposit paid*  

**Auto‑handoff**: When Reception finishes intake, Proposal is called in the *same turn*
so the user sees confirmation + proposal immediately.

## Proposal Engine (Minimal)

`proposal_engine` builds 3 tiers (基础/标准/升级) from:
- **人数** and optional **预算**
- per‑person baseline (¥300) with simple step‑ups
- deposit = 30%  

Selection uses **rules first**, **LLM fallback** (if enabled).

## Quickstart

## Quickstart

### 1) Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### 2) Run API
```bash
uvicorn app.main:app --reload --port 8000
```

### 3) Test with curl
```bash
curl -X POST http://localhost:8000/private_chef/message \
  -H "Content-Type: application/json" \
  -d '{"channel":"wechat","external_id":"wx_abc","source":"ad_1","text":"我想周六晚上请8个人吃饭，预算3000"}'
```

You should get a JSON response with `reply`, and updated `lead` / `offer` as the conversation progresses.

### 4) Local CLI Chat
```bash
python chat_sim.py
```
You’ll see an immediate welcome message, and proposals will be shown in the same turn
once intake is complete.

## Notes
- This is a **scaffold**. Many modules are intentionally minimal to keep the flow clear.
- Swap `app/storage/memory.py` with a DB-backed repo later without changing domain logic.
- LLM usage is optional; deterministic rules work without it.
