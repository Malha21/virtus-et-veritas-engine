from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    product_type: str = "course"
    target_audience: str | None = None
    tone_of_voice: str | None = None
    desired_duration: str | None = None
    description: str | None = None


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    target_audience: str | None = None
    tone_of_voice: str | None = None
    desired_duration: str | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    product_type: str
    target_audience: str | None
    tone_of_voice: str | None
    desired_duration: str | None
    description: str | None
    status: str
    processing_status: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ProjectListItem(BaseModel):
    id: UUID
    title: str
    product_type: str
    status: str
    processing_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    items: list[ProjectListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
