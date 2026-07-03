from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class InstructorAssetUpdate(BaseModel):
    description: str | None = None
    consent_confirmed: bool | None = None


class InstructorAssetResponse(BaseModel):
    id: UUID
    user_id: UUID
    instructor_profile_id: UUID | None
    asset_type: str
    original_filename: str | None
    stored_filename: str
    mime_type: str | None
    size_bytes: int | None
    description: str | None
    consent_confirmed: bool
    created_at: datetime
    updated_at: datetime | None
    download_url: str

    model_config = {"from_attributes": True}
