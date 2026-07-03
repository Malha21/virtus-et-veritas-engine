from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AudioGenerateRequest(BaseModel):
    generated_content_id: UUID | None = None
    block_index: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=255)
    text: str = Field(min_length=1, max_length=5000)
    voice: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    format: str = Field(default="mp3", max_length=20)


class GeneratedAudioResponse(BaseModel):
    id: UUID
    project_id: UUID
    generated_content_id: UUID | None
    block_index: int
    title: str | None
    voice: str | None
    model: str | None
    format: str
    duration_seconds: float | None
    status: str
    created_at: datetime
    download_url: str

    model_config = {"from_attributes": True}
