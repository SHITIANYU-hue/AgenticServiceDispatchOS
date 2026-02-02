from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
import os
import json
import logging
import urllib.request
import urllib.error

from app.config import settings
from .base import LLM
from .openai_llm import OpenAILLM

logger = logging.getLogger(__name__)


@dataclass
class AgentLLMProfile:
    system_prompt: str
    model: str
    temperature: float = 0.4


class LLMRegistry:
    def __init__(self, llm: LLM, profiles: Dict[str, AgentLLMProfile]):
        self._llm = llm
        self._profiles = profiles

    def get_llm(self, agent_name: str) -> LLM:
        return self._llm

    def get_profile(self, agent_name: str) -> AgentLLMProfile:
        return self._profiles.get(agent_name, self._profiles["default"])


def _validate_openai_key(api_key: str, base_url: str, timeout_sec: int) -> bool:
    # Minimal validation using the models endpoint.
    url = f"{base_url.rstrip('/')}/models"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            if resp.status != 200:
                logger.error("OpenAI key validation failed: status=%s", resp.status)
                return False
            # Read a bit to ensure the response is valid JSON.
            raw = resp.read().decode("utf-8")
            json.loads(raw)
            return True
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8") if exc.fp else str(exc)
        logger.error("OpenAI key validation HTTP error: %s", detail)
        return False
    except Exception as exc:
        logger.error("OpenAI key validation error: %s", exc)
        return False


def build_llm_registry() -> Optional[LLMRegistry]:
    # Prefer env var for key; fallback to config for local dev.
    api_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
    model = settings.openai_model
    if not api_key:
        logger.error("OPENAI_API_KEY missing; LLM disabled.")
        return None
    if not _validate_openai_key(api_key, settings.openai_base_url, settings.openai_timeout_sec):
        logger.error("OPENAI_API_KEY invalid or unreachable; LLM disabled.")
        return None
    logger.info("OpenAI key validated; LLM enabled for demo.")
    llm: LLM = OpenAILLM(
        api_key=api_key,
        model=model,
        base_url=settings.openai_base_url,
        timeout_sec=settings.openai_timeout_sec,
    )

    profiles = {
        "default": AgentLLMProfile(
            system_prompt="你是服务派单系统的助手，请用简洁中文回复。",
            model=model,
            temperature=0.4,
        ),
        "ReceptionAgent": AgentLLMProfile(
            system_prompt=(
                "你是接待助手。目标是补齐需求信息。每次最多询问2个问题，"
                "不要做承诺或保证，只收集信息并说明下一步。"
            ),
            model=model,
            temperature=0.3,
        ),
        "DispatchAgent": AgentLLMProfile(
            system_prompt=(
                "你是派单助手。请给出可成交回复，必须包含价格、定金、锁档时间和支付链接。"
                "语气专业、简洁。"
            ),
            model=model,
            temperature=0.3,
        ),
        "NegotiationAgent": AgentLLMProfile(
            system_prompt=(
                "你是议价助手。确保价格不低于底价，必要时给出替代方案。"
                "不做超出规则的承诺。"
            ),
            model=model,
            temperature=0.4,
        ),
        "OpsAgent": AgentLLMProfile(
            system_prompt=(
                "你是运营助手。确认支付、引导完成锁档。"
                "退款/改期必须遵循提供的政策信息。"
            ),
            model=model,
            temperature=0.3,
        ),
        "ProposalAgent": AgentLLMProfile(
            system_prompt=(
                "你是方案助理。清晰展示方案选项，引导用户选择或说明偏好。"
            ),
            model=model,
            temperature=0.4,
        ),
    }
    return LLMRegistry(llm, profiles)
