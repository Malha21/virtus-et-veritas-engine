from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict, Field

UserRole = Literal["admin", "member"]


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str

    model_config = ConfigDict(from_attributes=True)


class CurrentUserResponse(UserResponse):
    organization: OrganizationResponse


class AdminUserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)
    role: UserRole = "member"


class AdminUserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str
    status: str
    last_login_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
