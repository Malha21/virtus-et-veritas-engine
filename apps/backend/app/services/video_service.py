import uuid
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.generated_audio import GeneratedAudio
from app.models.generated_content import GeneratedContent
from app.models.generated_video import GeneratedVideo
from app.models.project import Project
from app.models.user import User
from app.schemas.video import GeneratedVideoGenerateRequest


def get_video_storage_dir(settings: Settings | None = None) -> Path:
    active_settings = settings or get_settings()
    path = Path(active_settings.storage_path) / "videos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_project_for_video(db: Session, current_user: User, project_id: UUID) -> Project:
    project = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
            Project.archived_at.is_(None),
            Project.deleted_at.is_(None),
        )
    ).scalar_one_or_none()

    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado.")

    return project


def get_audio_for_video(db: Session, project_id: UUID, audio_id: UUID | None) -> GeneratedAudio | None:
    if audio_id is None:
        return None

    audio = db.execute(
        select(GeneratedAudio).where(
            GeneratedAudio.id == audio_id,
            GeneratedAudio.project_id == project_id,
        )
    ).scalar_one_or_none()

    if audio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Áudio não encontrado.")

    return audio


def validate_lesson_for_video(db: Session, current_user: User, project_id: UUID, lesson_id: UUID | None) -> None:
    if lesson_id is None:
        return

    exists = db.execute(
        select(GeneratedContent.id).where(
            GeneratedContent.id == lesson_id,
            GeneratedContent.project_id == project_id,
            GeneratedContent.organization_id == current_user.organization_id,
            GeneratedContent.content_type == "lesson_script",
        )
    ).scalar_one_or_none()

    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula de origem não encontrada.")


def video_to_response_data(video: GeneratedVideo) -> dict[str, object]:
    return {
        "id": video.id,
        "project_id": video.project_id,
        "lesson_id": video.lesson_id,
        "module_id": video.module_id,
        "audio_id": video.audio_id,
        "avatar_id": video.avatar_id,
        "avatar_name": video.avatar_name,
        "provider": video.provider,
        "status": video.status,
        "resolution": video.resolution,
        "format": video.format,
        "file_name": video.file_name,
        "file_size_bytes": video.file_size_bytes,
        "duration_seconds": video.duration_seconds,
        "error_message": video.error_message,
        "extra_metadata": video.extra_metadata,
        "created_at": video.created_at,
        "updated_at": video.updated_at,
        "completed_at": video.completed_at,
        "download_url": f"/api/v1/projects/{video.project_id}/videos/{video.id}/download"
        if video.status == "completed" and video.file_path
        else None,
    }


def list_project_videos(db: Session, current_user: User, project_id: UUID) -> list[GeneratedVideo]:
    get_project_for_video(db, current_user, project_id)
    return list(
        db.execute(
            select(GeneratedVideo)
            .where(GeneratedVideo.project_id == project_id)
            .order_by(GeneratedVideo.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_video_for_project(db: Session, current_user: User, project_id: UUID, video_id: UUID) -> GeneratedVideo:
    get_project_for_video(db, current_user, project_id)
    video = db.execute(
        select(GeneratedVideo).where(
            GeneratedVideo.id == video_id,
            GeneratedVideo.project_id == project_id,
        )
    ).scalar_one_or_none()

    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vídeo não encontrado.")

    return video


def create_mock_video_file(video_dir: Path, project_id: UUID, video_format: str, payload_text: str) -> tuple[str, Path, int]:
    safe_format = video_format.lower().strip(".") or "mp4"
    filename = f"{project_id}-mock-video-{uuid.uuid4().hex}.{safe_format}"
    file_path = video_dir / filename
    file_path.write_bytes(payload_text.encode("utf-8"))
    return filename, file_path, file_path.stat().st_size


def generate_mock_video(
    db: Session,
    current_user: User,
    project_id: UUID,
    payload: GeneratedVideoGenerateRequest,
    settings: Settings | None = None,
) -> GeneratedVideo:
    active_settings = settings or get_settings()
    project = get_project_for_video(db, current_user, project_id)
    audio = get_audio_for_video(db, project.id, payload.audio_id)
    validate_lesson_for_video(db, current_user, project.id, payload.lesson_id)

    video_format = (payload.format or active_settings.video_default_format or "mp4").lower()
    if video_format != "mp4":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato de vídeo inválido nesta versão.")

    resolution = payload.resolution or active_settings.video_default_resolution or "1080p"
    provider = active_settings.video_provider or "mock"
    video_dir = get_video_storage_dir(active_settings)
    mock_text = "\n".join(
        [
            "VVE Engine mock video placeholder",
            f"project_id={project.id}",
            f"lesson_id={payload.lesson_id or ''}",
            f"module_id={payload.module_id or ''}",
            f"audio_id={audio.id if audio else ''}",
            f"avatar_id={payload.avatar_id or ''}",
            f"avatar_name={payload.avatar_name or ''}",
            f"resolution={resolution}",
            f"format={video_format}",
            "provider=mock",
        ]
    )
    file_name, file_path, file_size = create_mock_video_file(video_dir, project.id, video_format, mock_text)
    now = datetime.now(UTC)

    video = GeneratedVideo(
        project_id=project.id,
        lesson_id=payload.lesson_id,
        module_id=payload.module_id,
        audio_id=audio.id if audio else None,
        avatar_id=payload.avatar_id,
        avatar_name=payload.avatar_name,
        provider=provider,
        status="completed",
        resolution=resolution,
        format=video_format,
        file_path=str(file_path),
        file_name=file_name,
        file_size_bytes=file_size,
        duration_seconds=int(audio.duration_seconds or 0) if audio else None,
        extra_metadata={
            "mock": True,
            "source": "fase_18_0",
            "audio_title": audio.title if audio else None,
            **(payload.extra_metadata or {}),
        },
        completed_at=now,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def get_video_download_path(db: Session, current_user: User, project_id: UUID, video_id: UUID) -> tuple[GeneratedVideo, Path]:
    video = get_video_for_project(db, current_user, project_id, video_id)
    if video.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vídeo ainda não está pronto para download.")
    if not video.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de vídeo não encontrado.")

    video_dir = get_video_storage_dir().resolve()
    file_path = Path(video.file_path).resolve()
    if video_dir not in file_path.parents:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Caminho de vídeo inválido.")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de vídeo não encontrado.")

    return video, file_path


def delete_project_video(db: Session, current_user: User, project_id: UUID, video_id: UUID) -> None:
    video = get_video_for_project(db, current_user, project_id, video_id)
    if video.file_path:
        video_dir = get_video_storage_dir().resolve()
        file_path = Path(video.file_path).resolve()
        if video_dir in file_path.parents and file_path.exists() and file_path.is_file():
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass

    db.delete(video)
    db.commit()
