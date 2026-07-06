from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.video import GeneratedVideoGenerateRequest, GeneratedVideoReviewUpdateRequest
from app.services.video_service import (
    delete_project_video,
    generate_video,
    get_video_download_path,
    get_video_for_project,
    list_project_videos,
    refresh_video_status,
    update_video_review,
    video_to_response_data,
)

router = APIRouter(prefix="/projects/{project_id}/videos", tags=["videos"])


@router.get("")
def get_project_videos(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    videos = list_project_videos(db, current_user, project_id)
    return {"success": True, "data": [video_to_response_data(video) for video in videos]}


@router.post("/generate")
def post_generate_video(
    project_id: UUID,
    payload: GeneratedVideoGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    video = generate_video(db, current_user, project_id, payload)
    return {"success": True, "data": video_to_response_data(video)}


@router.post("/{video_id}/refresh-status")
def post_refresh_video_status(
    project_id: UUID,
    video_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    video = refresh_video_status(db, current_user, project_id, video_id)
    return {"success": True, "data": video_to_response_data(video)}


@router.patch("/{video_id}/review")
def patch_video_review(
    project_id: UUID,
    video_id: UUID,
    payload: GeneratedVideoReviewUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    video = update_video_review(db, current_user, project_id, video_id, payload)
    return {"success": True, "data": video_to_response_data(video)}


@router.get("/{video_id}")
def get_project_video(
    project_id: UUID,
    video_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    video = get_video_for_project(db, current_user, project_id, video_id)
    return {"success": True, "data": video_to_response_data(video)}


@router.get("/{video_id}/download")
def download_project_video(
    project_id: UUID,
    video_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    video, file_path = get_video_download_path(db, current_user, project_id, video_id)
    filename = video.file_name or f"video-{video.id}.{video.format}"
    return FileResponse(path=file_path, media_type="video/mp4", filename=filename)


@router.delete("/{video_id}")
def delete_video(
    project_id: UUID,
    video_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    delete_project_video(db, current_user, project_id, video_id)
    return {"success": True, "data": {"message": "Video excluido com sucesso."}}
