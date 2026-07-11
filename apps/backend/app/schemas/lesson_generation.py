from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

LESSON_GENERATION_STATUSES = {"pending", "processing", "completed", "failed", "cancelled"}

LESSON_GENERATION_VALIDATION_STATUSES = {"pending", "valid", "invalid", "requires_review", "approved"}


class LessonGenerationBase(BaseModel):
    version: int = Field(default=1, gt=0)
    generated_content: str | None = None
    structured_content: dict[str, Any] | None = None
    word_count: int | None = Field(default=None, ge=0)
    estimated_duration_seconds: int | None = Field(default=None, ge=0)
    source_item_count: int = Field(default=0, ge=0)
    generation_status: str = "pending"
    validation_status: str = "pending"
    model_name: str | None = None
    prompt_version: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_statuses(self) -> "LessonGenerationBase":
        if self.generation_status not in LESSON_GENERATION_STATUSES:
            raise ValueError(f"generation_status invalido: {self.generation_status}")
        if self.validation_status not in LESSON_GENERATION_VALIDATION_STATUSES:
            raise ValueError(f"validation_status invalido: {self.validation_status}")
        return self


class LessonGenerationCreate(LessonGenerationBase):
    lesson_content_id: UUID


class LessonGenerationUpdate(BaseModel):
    generated_content: str | None = None
    structured_content: dict[str, Any] | None = None
    word_count: int | None = Field(default=None, ge=0)
    estimated_duration_seconds: int | None = Field(default=None, ge=0)
    source_item_count: int | None = Field(default=None, ge=0)
    generation_status: str | None = None
    validation_status: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_statuses(self) -> "LessonGenerationUpdate":
        if self.generation_status is not None and self.generation_status not in LESSON_GENERATION_STATUSES:
            raise ValueError(f"generation_status invalido: {self.generation_status}")
        if (
            self.validation_status is not None
            and self.validation_status not in LESSON_GENERATION_VALIDATION_STATUSES
        ):
            raise ValueError(f"validation_status invalido: {self.validation_status}")
        return self


class LessonGenerationResponse(LessonGenerationBase):
    id: UUID
    lesson_content_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonGenerationListResponse(BaseModel):
    items: list[LessonGenerationResponse]


class LessonGenerationFilter(BaseModel):
    lesson_content_id: UUID | None = None
    generation_status: str | None = None
    validation_status: str | None = None
