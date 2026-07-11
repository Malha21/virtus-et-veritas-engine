from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

PipelineScope = Literal["lesson", "module", "course"]


class VideoPipelineJobCreate(BaseModel):
    scope: PipelineScope
    module_index: int | None = Field(default=None, ge=1)
    lesson_id: UUID | None = None
    provider: str | None = Field(default=None, max_length=50)
    video_avatar_id: UUID | None = None
    skip_existing_audio: bool = True
    skip_existing_video: bool = True
    force_regenerate_audio: bool = False
    force_regenerate_video: bool = False

    @model_validator(mode="after")
    def validate_scope_fields(self) -> "VideoPipelineJobCreate":
        if self.scope == "lesson" and self.lesson_id is None:
            raise ValueError("lesson_id é obrigatório para escopo 'lesson'.")
        if self.scope == "module" and self.module_index is None:
            raise ValueError("module_index é obrigatório para escopo 'module'.")
        return self


class VideoPipelineJobItemRead(BaseModel):
    id: UUID
    job_id: UUID
    project_id: UUID
    lesson_content_id: UUID | None
    module_index: int | None
    lesson_index: int | None
    lesson_title: str | None
    status: str
    generated_audio_id: UUID | None
    generated_video_id: UUID | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class VideoPipelineJobRead(BaseModel):
    id: UUID
    project_id: UUID
    scope: str
    module_index: int | None
    lesson_id: UUID | None
    lesson_index: int | None
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    current_item_label: str | None
    provider: str | None
    video_avatar_id: UUID | None
    skip_existing_audio: bool
    skip_existing_video: bool
    force_regenerate_audio: bool
    force_regenerate_video: bool
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime | None
    items: list[VideoPipelineJobItemRead] = []

    model_config = ConfigDict(from_attributes=True)


class VideoPipelineJobListRead(BaseModel):
    items: list[VideoPipelineJobRead]
