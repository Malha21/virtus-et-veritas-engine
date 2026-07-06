from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class VideoAvatarCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., max_length=50)
    avatar_id: str | None = Field(default=None, max_length=255)
    source_image_url: str | None = Field(default=None, max_length=2000)
    source_video_url: str | None = Field(default=None, max_length=2000)
    default_model: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True
    is_default: bool = False
    extra_metadata: dict[str, Any] | None = None


class VideoAvatarUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    provider: str | None = Field(default=None, max_length=50)
    avatar_id: str | None = Field(default=None, max_length=255)
    source_image_url: str | None = Field(default=None, max_length=2000)
    source_video_url: str | None = Field(default=None, max_length=2000)
    default_model: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    is_default: bool | None = None
    extra_metadata: dict[str, Any] | None = None


class VideoAvatarRead(BaseModel):
    id: UUID
    project_id: UUID | None
    name: str
    provider: str
    avatar_id: str | None
    source_image_url: str | None
    source_video_url: str | None
    default_model: str | None
    description: str | None
    is_active: bool
    is_default: bool
    extra_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime | None
