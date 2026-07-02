from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectFileResponse(BaseModel):
    id: UUID
    project_id: UUID
    file_type: str
    original_filename: str
    mime_type: str | None
    file_size: int | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectFileListResponse(BaseModel):
    items: list[ProjectFileResponse]
