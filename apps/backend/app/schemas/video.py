from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class GeneratedVideoGenerateRequest(BaseModel):
    lesson_id: UUID | None = None
    module_id: UUID | None = None
    audio_id: UUID | None = None
    video_avatar_id: UUID | None = None
    provider: str | None = Field(default=None, max_length=50)
    avatar_id: str | None = Field(default=None, max_length=255)
    avatar_name: str | None = Field(default=None, max_length=255)
    source_image_url: str | None = Field(default=None, max_length=2000)
    source_video_url: str | None = Field(default=None, max_length=2000)
    model: str | None = Field(default=None, max_length=100)
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
    provider_job_id: str | None
    remote_video_url: str | None
    source_image_url: str | None
    source_video_url: str | None
    last_status_check_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    completed_at: datetime | None
    generation_started_at: datetime | None
    generation_completed_at: datetime | None
    provider_latency_seconds: float | None
    estimated_cost_usd: float | None
    quality_rating: int | None
    quality_notes: str | None
    download_url: str | None


class GeneratedVideoListResponse(BaseModel):
    items: list[GeneratedVideoRead]


class GeneratedVideoReviewUpdateRequest(BaseModel):
    quality_rating: int | None = Field(default=None, ge=1, le=5)
    quality_notes: str | None = Field(default=None, max_length=4000)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
