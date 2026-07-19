from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.project import AIProviderChoice


class UserAICredentialUpsert(BaseModel):
    api_key: str = Field(min_length=8, max_length=500)


class UserAICredentialResponse(BaseModel):
    id: UUID
    provider_type: AIProviderChoice
    key_last_four: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
