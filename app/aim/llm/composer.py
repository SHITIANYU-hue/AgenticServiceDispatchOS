from __future__ import annotations
import json
from typing import Any, Dict, Optional

from app.config import settings
from .registry import LLMRegistry


def compose_reply(
    llm_registry: Optional[LLMRegistry],
    agent_name: str,
    user_text: str,
    context: Dict[str, Any],
    fallback_reply: str,
) -> str:
    # Compose a reply via LLM; return fallback on error.
    if llm_registry is None or not settings.enable_llm:
        return fallback_reply
    profile = llm_registry.get_profile(agent_name)
    llm = llm_registry.get_llm(agent_name)

    payload = {
        "user_text": user_text,
        "context": context,
    }
    user_prompt = (
        "请根据以下信息生成回复，必须遵循系统要求。\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    messages = [
        {"role": "system", "content": profile.system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        reply = llm.chat(messages, temperature=profile.temperature, model=profile.model)
    except Exception:
        return fallback_reply
    if not reply:
        return fallback_reply
    return reply
