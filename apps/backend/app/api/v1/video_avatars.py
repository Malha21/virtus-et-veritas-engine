from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.video_avatar import GeneratedVideoAvatar
from app.schemas.video_avatar import VideoAvatarCreate, VideoAvatarRead, VideoAvatarUpdate
from app.services.video_avatar_service import (
    create_video_avatar,
    deactivate_video_avatar,
    get_avatar_for_project,
    list_project_avatars,
    update_video_avatar,
)

router = APIRouter(prefix="/projects/{project_id}/video-avatars", tags=["video-avatars"])


def avatar_to_response_data(avatar: GeneratedVideoAvatar) -> dict[str, object]:
    return VideoAvatarRead.model_validate(avatar, from_attributes=True).model_dump(mode="json")


@router.get("")
def get_project_video_avatars(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    avatars = list_project_avatars(db, current_user, project_id)
    return {"success": True, "data": [avatar_to_response_data(avatar) for avatar in avatars]}


@router.post("")
def post_video_avatar(
    project_id: UUID,
    payload: VideoAvatarCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    avatar = create_video_avatar(db, current_user, project_id, payload)
    return {"success": True, "data": avatar_to_response_data(avatar)}


@router.get("/{avatar_id}")
def get_video_avatar(
    project_id: UUID,
    avatar_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    avatar = get_avatar_for_project(db, current_user, project_id, avatar_id)
    return {"success": True, "data": avatar_to_response_data(avatar)}


@router.patch("/{avatar_id}")
def patch_video_avatar(
    project_id: UUID,
    avatar_id: UUID,
    payload: VideoAvatarUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    avatar = update_video_avatar(db, current_user, project_id, avatar_id, payload)
    return {"success": True, "data": avatar_to_response_data(avatar)}


@router.delete("/{avatar_id}")
def delete_video_avatar(
    project_id: UUID,
    avatar_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    deactivate_video_avatar(db, current_user, project_id, avatar_id)
    return {"success": True, "data": {"message": "Avatar desativado com sucesso."}}
