from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

from .base import LLM


class OpenAILLM(LLM):
    def __init__(self, api_key: str, model: str, base_url: str, timeout_sec: int = 30):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # Call OpenAI Responses API with a simple message list.
        model = kwargs.get("model") or self.model
        payload: Dict[str, Any] = {"model": model, "input": messages}
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "text_format" in kwargs:
            payload["text"] = {"format": kwargs["text_format"]}

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/responses",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8") if exc.fp else str(exc)
            raise RuntimeError(f"openai_http_error: {detail}") from exc
        except Exception as exc:
            raise RuntimeError(f"openai_request_error: {exc}") from exc

        data = json.loads(raw)
        return _extract_text(data)


def _extract_text(data: Dict[str, Any]) -> str:
    # Extract assistant text from Responses API payload.
    output = data.get("output", [])
    parts: List[str] = []
    for item in output:
        if item.get("type") != "message":
            continue
        if item.get("role") != "assistant":
            continue
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                parts.append(text)
    if parts:
        return "".join(parts)
    # Fallback for other formats.
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text
    return ""
