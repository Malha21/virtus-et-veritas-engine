from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProcessingJobResponse(BaseModel):
    id: UUID
    project_id: UUID
    project_file_id: UUID | None = None
    lesson_content_id: UUID | None = None
    coverage_plan_lesson_id: UUID | None = None
    job_type: str
    status: str
    progress: int
    current_step: str | None
    total_items: int | None = None
    processed_items: int | None = None
    failed_items: int | None = None
    current_item: str | None = None
    message: str | None
    attempts: int
    max_attempts: int
    error_message: str | None
    result_json: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProcessingJobProgressUpdate(BaseModel):
    """Validacao de atualizacoes de progresso para jobs longos e retomaveis (fase 19.1)."""

    progress: int | None = Field(default=None, ge=0, le=100)
    total_items: int | None = Field(default=None, ge=0)
    processed_items: int | None = Field(default=None, ge=0)
    failed_items: int | None = Field(default=None, ge=0)
    current_item: str | None = None

    @model_validator(mode="after")
    def validate_item_counts(self) -> "ProcessingJobProgressUpdate":
        if (
            self.total_items is not None
            and self.processed_items is not None
            and self.processed_items > self.total_items
        ):
            raise ValueError("processed_items nao pode ser maior que total_items.")
        return self


class ProcessingStatusResponse(BaseModel):
    project_id: UUID
    processing_status: str
    progress: int
    current_step: str
    updated_at: datetime


class ProcessingLogResponse(BaseModel):
    id: UUID
    level: str
    message: str
    context_json: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProcessingLogListResponse(BaseModel):
    items: list[ProcessingLogResponse]


class StartProcessingResponse(BaseModel):
    project_id: UUID
    processing_status: str
    message: str
    job_id: UUID


class StartAIJobResponse(BaseModel):
    job_id: UUID
    status: str
    message: str
