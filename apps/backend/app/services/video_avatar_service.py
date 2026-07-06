from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.user import User
from app.models.video_avatar import GeneratedVideoAvatar
from app.schemas.video_avatar import VideoAvatarCreate, VideoAvatarUpdate

VALID_VIDEO_PROVIDERS = {"mock", "heygen", "did", "sync"}


def validate_video_avatar_provider(provider: str) -> str:
    normalized = (provider or "").lower().strip()
    if normalized not in VALID_VIDEO_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider de avatar invalido.")
    return normalized


def validate_video_avatar_fields(
    provider: str,
    avatar_id: str | None,
    source_image_url: str | None,
    source_video_url: str | None,
) -> None:
    if provider == "heygen" and not (avatar_id or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar HeyGen precisa de avatar_id.",
        )
    if provider == "did" and not (source_image_url or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar D-ID precisa de source_image_url.",
        )
    if provider == "sync" and not (source_video_url or "").strip() and not (source_image_url or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar Sync Labs precisa de source_video_url ou source_image_url.",
        )


def get_project_for_avatar(db: Session, current_user: User, project_id: UUID) -> Project:
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


def get_avatar_for_project(db: Session, current_user: User, project_id: UUID, avatar_id: UUID) -> GeneratedVideoAvatar:
    get_project_for_avatar(db, current_user, project_id)
    avatar = db.execute(
        select(GeneratedVideoAvatar).where(
            GeneratedVideoAvatar.id == avatar_id,
            GeneratedVideoAvatar.project_id == project_id,
        )
    ).scalar_one_or_none()

    if avatar is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar nao encontrado.")

    return avatar


def list_project_avatars(db: Session, current_user: User, project_id: UUID) -> list[GeneratedVideoAvatar]:
    get_project_for_avatar(db, current_user, project_id)
    return list(
        db.execute(
            select(GeneratedVideoAvatar)
            .where(GeneratedVideoAvatar.project_id == project_id)
            .order_by(GeneratedVideoAvatar.provider.asc(), GeneratedVideoAvatar.created_at.desc())
        )
        .scalars()
        .all()
    )


def clear_other_defaults(db: Session, project_id: UUID, provider: str, keep_avatar_id: UUID) -> None:
    others = db.execute(
        select(GeneratedVideoAvatar).where(
            GeneratedVideoAvatar.project_id == project_id,
            GeneratedVideoAvatar.provider == provider,
            GeneratedVideoAvatar.id != keep_avatar_id,
            GeneratedVideoAvatar.is_default.is_(True),
        )
    ).scalars().all()
    for other in others:
        other.is_default = False
        db.add(other)


def create_video_avatar(
    db: Session,
    current_user: User,
    project_id: UUID,
    payload: VideoAvatarCreate,
) -> GeneratedVideoAvatar:
    project = get_project_for_avatar(db, current_user, project_id)
    provider = validate_video_avatar_provider(payload.provider)
    validate_video_avatar_fields(provider, payload.avatar_id, payload.source_image_url, payload.source_video_url)

    avatar = GeneratedVideoAvatar(
        project_id=project.id,
        name=payload.name.strip(),
        provider=provider,
        avatar_id=payload.avatar_id,
        source_image_url=payload.source_image_url,
        source_video_url=payload.source_video_url,
        default_model=payload.default_model,
        description=payload.description,
        is_active=payload.is_active,
        is_default=payload.is_default,
        extra_metadata=payload.extra_metadata,
    )
    db.add(avatar)
    db.flush()

    if avatar.is_default:
        clear_other_defaults(db, project.id, provider, avatar.id)

    db.commit()
    db.refresh(avatar)
    return avatar


def update_video_avatar(
    db: Session,
    current_user: User,
    project_id: UUID,
    avatar_id: UUID,
    payload: VideoAvatarUpdate,
) -> GeneratedVideoAvatar:
    avatar = get_avatar_for_project(db, current_user, project_id, avatar_id)
    updates = payload.model_dump(exclude_unset=True)

    provider = avatar.provider
    if "provider" in updates:
        provider = validate_video_avatar_provider(updates["provider"])
        updates["provider"] = provider

    merged_avatar_id = updates.get("avatar_id", avatar.avatar_id)
    merged_source_image_url = updates.get("source_image_url", avatar.source_image_url)
    merged_source_video_url = updates.get("source_video_url", avatar.source_video_url)
    validate_video_avatar_fields(provider, merged_avatar_id, merged_source_image_url, merged_source_video_url)

    if "name" in updates and updates["name"] is not None:
        updates["name"] = updates["name"].strip()

    for field, value in updates.items():
        setattr(avatar, field, value)

    db.add(avatar)
    db.flush()

    if avatar.is_default:
        clear_other_defaults(db, avatar.project_id, avatar.provider, avatar.id)

    db.commit()
    db.refresh(avatar)
    return avatar


def deactivate_video_avatar(db: Session, current_user: User, project_id: UUID, avatar_id: UUID) -> None:
    avatar = get_avatar_for_project(db, current_user, project_id, avatar_id)
    avatar.is_active = False
    avatar.is_default = False
    db.add(avatar)
    db.commit()


def get_active_avatar_for_generation(db: Session, project_id: UUID, avatar_id: UUID) -> GeneratedVideoAvatar:
    avatar = db.execute(
        select(GeneratedVideoAvatar).where(
            GeneratedVideoAvatar.id == avatar_id,
            GeneratedVideoAvatar.project_id == project_id,
        )
    ).scalar_one_or_none()

    if avatar is None or not avatar.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar nao encontrado ou inativo.")

    return avatar
