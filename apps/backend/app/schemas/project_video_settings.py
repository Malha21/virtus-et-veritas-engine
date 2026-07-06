from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectVideoSettingsRead(BaseModel):
    id: UUID | None
    project_id: UUID
    default_provider: str | None
    default_mock_avatar_id: UUID | None
    default_heygen_avatar_id: UUID | None
    default_did_avatar_id: UUID | None
    default_sync_avatar_id: UUID | None
    default_resolution: str
    default_format: str
    auto_download_completed_videos: bool
    created_at: datetime | None
    updated_at: datetime | None


class ProjectVideoSettingsUpdate(BaseModel):
    default_provider: str | None = Field(default=None, max_length=50)
    default_mock_avatar_id: UUID | None = None
    default_heygen_avatar_id: UUID | None = None
    default_did_avatar_id: UUID | None = None
    default_sync_avatar_id: UUID | None = None
    default_resolution: str | None = Field(default=None, max_length=50)
    default_format: str | None = Field(default=None, max_length=20)
    auto_download_completed_videos: bool | None = None
