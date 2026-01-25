from pydantic import BaseModel

class Settings(BaseModel):
    app_name: str = "Agentic Service Dispatch OS"
    tenant_id: str = "default"

settings = Settings()
