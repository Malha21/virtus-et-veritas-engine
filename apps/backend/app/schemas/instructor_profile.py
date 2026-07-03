from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class InstructorProfileBase(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    bio: str | None = None
    teaching_style: str | None = None
    voice_provider: str | None = Field(default=None, max_length=100)
    voice_id: str | None = Field(default=None, max_length=255)
    voice_name: str | None = Field(default=None, max_length=255)
    voice_sample_notes: str | None = None
    avatar_provider: str | None = Field(default=None, max_length=100)
    avatar_id: str | None = Field(default=None, max_length=255)
    avatar_name: str | None = Field(default=None, max_length=255)
    avatar_style: str | None = None
    avatar_image_path: str | None = Field(default=None, max_length=1000)
    consent_voice_clone: bool = False
    consent_avatar_use: bool = False
    consent_terms_text: str | None = None


class InstructorProfileCreate(InstructorProfileBase):
    pass


class InstructorProfileUpdate(InstructorProfileBase):
    pass


class InstructorProfileResponse(InstructorProfileBase):
    id: UUID
    user_id: UUID
    consent_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
