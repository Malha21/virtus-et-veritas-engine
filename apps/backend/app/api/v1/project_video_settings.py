from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.project_video_settings import ProjectVideoSettingsRead, ProjectVideoSettingsUpdate
from app.services.project_video_settings_service import (
    get_project_video_settings,
    update_project_video_settings,
)

router = APIRouter(prefix="/projects/{project_id}/video-settings", tags=["video-settings"])


@router.get("")
def get_video_settings(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    data = get_project_video_settings(db, current_user, project_id)
    return {"success": True, "data": ProjectVideoSettingsRead.model_validate(data).model_dump(mode="json")}


@router.patch("")
def patch_video_settings(
    project_id: UUID,
    payload: ProjectVideoSettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    data = update_project_video_settings(db, current_user, project_id, payload)
    return {"success": True, "data": ProjectVideoSettingsRead.model_validate(data).model_dump(mode="json")}
