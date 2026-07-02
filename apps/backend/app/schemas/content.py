from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GeneratedContentUpdate(BaseModel):
    title: str | None = None
    content_json: dict[str, Any] | None = None
    content_text: str | None = None
    status: str | None = None


class GeneratedContentResponse(BaseModel):
    id: UUID
    project_id: UUID
    organization_id: UUID
    content_type: str
    title: str | None
    version: int
    language: str
    content_json: dict[str, Any] | None
    content_text: str | None
    status: str
    created_by_ai_provider_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GeneratedContentListResponse(BaseModel):
    items: list[GeneratedContentResponse]
