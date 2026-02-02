from pydantic import BaseModel

class Settings(BaseModel):
    # Centralized app settings (simple, no env binding yet).
    app_name: str = "Agentic Service Dispatch OS"
    tenant_id: str = "default"
    booking_hold_minutes: int = 60
    # Debug flag: disable LLM replies to validate workflow with deterministic templates.
    enable_llm: bool = False
    # Use LLM for requirement extraction when regex rules are insufficient.
    enable_llm_extract: bool = True
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_sec: int = 30

settings = Settings()
