from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProcessingJobResponse(BaseModel):
    id: UUID
    project_id: UUID
    job_type: str
    status: str
    progress: int
    current_step: str | None
    message: str | None
    attempts: int
    max_attempts: int
    error_message: str | None
    result_json: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
