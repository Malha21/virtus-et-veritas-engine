from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict


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
