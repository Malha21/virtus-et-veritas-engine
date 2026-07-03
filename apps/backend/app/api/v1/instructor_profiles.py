from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.instructor_profile import InstructorProfile
from app.models.user import User
from app.schemas.instructor_profile import (
    InstructorProfileCreate,
    InstructorProfileResponse,
    InstructorProfileUpdate,
)

router = APIRouter(prefix="/instructor-profile", tags=["instructor-profile"])


def get_profile_by_user(db: Session, current_user: User) -> InstructorProfile | None:
    return db.execute(
        select(InstructorProfile).where(InstructorProfile.user_id == current_user.id)
    ).scalar_one_or_none()


def apply_profile_payload(
    profile: InstructorProfile,
    payload: InstructorProfileCreate | InstructorProfileUpdate,
) -> None:
    previous_voice_consent = bool(profile.consent_voice_clone)
    previous_avatar_consent = bool(profile.consent_avatar_use)
    updates = payload.model_dump()

    for field, value in updates.items():
        setattr(profile, field, value)

    if (
        previous_voice_consent != profile.consent_voice_clone
        or previous_avatar_consent != profile.consent_avatar_use
    ):
        profile.consent_updated_at = datetime.now(UTC)


def profile_response(profile: InstructorProfile) -> dict[str, object]:
    return InstructorProfileResponse.model_validate(profile).model_dump(mode="json")


@router.get("")
def get_instructor_profile(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    profile = get_profile_by_user(db, current_user)
    return {"success": True, "data": profile_response(profile) if profile else None}


@router.post("")
def create_instructor_profile(
    payload: InstructorProfileCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    existing_profile = get_profile_by_user(db, current_user)
    if existing_profile is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Perfil do instrutor já existe.",
        )

    profile = InstructorProfile(user_id=current_user.id)
    apply_profile_payload(profile, payload)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return {"success": True, "data": profile_response(profile)}


@router.put("")
def upsert_instructor_profile(
    payload: InstructorProfileUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    profile = get_profile_by_user(db, current_user)
    if profile is None:
        profile = InstructorProfile(user_id=current_user.id)

    apply_profile_payload(profile, payload)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return {"success": True, "data": profile_response(profile)}
