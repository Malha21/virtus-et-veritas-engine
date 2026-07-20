from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

CredentialProviderChoice = Literal["openai", "gemini", "anthropic"]


class UserAICredentialUpsert(BaseModel):
    api_key: str = Field(min_length=8, max_length=500)
    base_url: str | None = Field(default=None, max_length=500)

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value.rstrip("/") or None


class UserAICredentialResponse(BaseModel):
    id: UUID
    provider_type: CredentialProviderChoice
    key_last_four: str
    base_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
