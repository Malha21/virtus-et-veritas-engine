from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class GeneratedVideoGenerateRequest(BaseModel):
    lesson_id: UUID | None = None
    module_id: UUID | None = None
    audio_id: UUID | None = None
    avatar_id: str | None = Field(default=None, max_length=255)
    avatar_name: str | None = Field(default=None, max_length=255)
    resolution: str | None = Field(default=None, max_length=50)
    format: str | None = Field(default=None, max_length=20)
    extra_metadata: dict[str, Any] | None = None


class GeneratedVideoRead(BaseModel):
    id: UUID
    project_id: UUID
    lesson_id: UUID | None
    module_id: UUID | None
    audio_id: UUID | None
    avatar_id: str | None
    avatar_name: str | None
    provider: str
    status: str
    resolution: str
    format: str
    file_name: str | None
    file_size_bytes: int | None
    duration_seconds: int | None
    error_message: str | None
    extra_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime | None
    completed_at: datetime | None
    download_url: str | None


class GeneratedVideoListResponse(BaseModel):
    items: list[GeneratedVideoRead]
