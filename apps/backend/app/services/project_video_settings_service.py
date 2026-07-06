from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_video_settings import ProjectVideoSettings
from app.models.user import User
from app.models.video_avatar import GeneratedVideoAvatar
from app.schemas.project_video_settings import ProjectVideoSettingsUpdate

VALID_VIDEO_PROVIDERS = {"mock", "heygen", "did", "sync"}
DEFAULT_RESOLUTION = "1080p"
DEFAULT_FORMAT = "mp4"

AVATAR_FIELD_BY_PROVIDER = {
    "mock": "default_mock_avatar_id",
    "heygen": "default_heygen_avatar_id",
    "did": "default_did_avatar_id",
    "sync": "default_sync_avatar_id",
}


def get_project_for_settings(db: Session, current_user: User, project_id: UUID) -> Project:
    project = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
            Project.archived_at.is_(None),
            Project.deleted_at.is_(None),
        )
    ).scalar_one_or_none()

    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto nao encontrado.")

    return project


def get_project_video_settings_row(db: Session, project_id: UUID) -> ProjectVideoSettings | None:
    return db.execute(
        select(ProjectVideoSettings).where(ProjectVideoSettings.project_id == project_id)
    ).scalar_one_or_none()


def pick_default_avatar_id(settings_row: ProjectVideoSettings, provider: str) -> UUID | None:
    field = AVATAR_FIELD_BY_PROVIDER.get(provider)
    if not field:
        return None
    return getattr(settings_row, field)


def settings_to_dict(row: ProjectVideoSettings) -> dict[str, object]:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "default_provider": row.default_provider,
        "default_mock_avatar_id": row.default_mock_avatar_id,
        "default_heygen_avatar_id": row.default_heygen_avatar_id,
        "default_did_avatar_id": row.default_did_avatar_id,
        "default_sync_avatar_id": row.default_sync_avatar_id,
        "default_resolution": row.default_resolution,
        "default_format": row.default_format,
        "auto_download_completed_videos": row.auto_download_completed_videos,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def build_default_settings_response(project_id: UUID) -> dict[str, object]:
    return {
        "id": None,
        "project_id": project_id,
        "default_provider": None,
        "default_mock_avatar_id": None,
        "default_heygen_avatar_id": None,
        "default_did_avatar_id": None,
        "default_sync_avatar_id": None,
        "default_resolution": DEFAULT_RESOLUTION,
        "default_format": DEFAULT_FORMAT,
        "auto_download_completed_videos": True,
        "created_at": None,
        "updated_at": None,
    }


def get_project_video_settings(db: Session, current_user: User, project_id: UUID) -> dict[str, object]:
    project = get_project_for_settings(db, current_user, project_id)
    row = get_project_video_settings_row(db, project.id)
    if row is None:
        return build_default_settings_response(project.id)
    return settings_to_dict(row)


def validate_default_avatar(db: Session, project_id: UUID, provider: str, avatar_id: UUID | None) -> None:
    if avatar_id is None:
        return

    avatar = db.execute(
        select(GeneratedVideoAvatar).where(GeneratedVideoAvatar.id == avatar_id)
    ).scalar_one_or_none()

    if avatar is None or not avatar.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar padrao nao encontrado ou inativo.",
        )
    if avatar.project_id is not None and avatar.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar padrao nao pertence a este projeto.",
        )
    if avatar.provider != provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Avatar selecionado nao corresponde ao provider {provider}.",
        )


def update_project_video_settings(
    db: Session,
    current_user: User,
    project_id: UUID,
    payload: ProjectVideoSettingsUpdate,
) -> dict[str, object]:
    project = get_project_for_settings(db, current_user, project_id)
    updates = payload.model_dump(exclude_unset=True)

    if "default_provider" in updates and updates["default_provider"] is not None:
        provider = updates["default_provider"].lower().strip()
        if provider not in VALID_VIDEO_PROVIDERS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider padrao invalido.")
        updates["default_provider"] = provider

    for provider, field in AVATAR_FIELD_BY_PROVIDER.items():
        if field in updates:
            validate_default_avatar(db, project.id, provider, updates[field])

    row = get_project_video_settings_row(db, project.id)
    if row is None:
        row = ProjectVideoSettings(project_id=project.id)
        db.add(row)

    for field, value in updates.items():
        setattr(row, field, value)

    db.commit()
    db.refresh(row)
    return settings_to_dict(row)
