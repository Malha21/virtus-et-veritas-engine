import uuid
import shutil
import subprocess
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
from app.providers.video import did, heygen
from app.providers.video import sync as sync_provider
from app.providers.video.base import VideoProviderError
from app.schemas.video import GeneratedVideoGenerateRequest
from app.services.signed_url_service import generate_audio_asset_token

MOCK_VIDEO_UNAVAILABLE_MESSAGE = "Arquivo MP4 real ainda não disponível para este vídeo mock."
VIDEO_FILE_UNAVAILABLE_MESSAGE = "Arquivo MP4 ainda não disponível para este vídeo."


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
    has_download = video.status == "completed" and bool(video.file_path) and is_valid_mp4_file(Path(video.file_path))
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
        "provider_job_id": video.provider_job_id,
        "remote_video_url": video.remote_video_url,
        "source_image_url": video.source_image_url,
        "source_video_url": video.source_video_url,
        "last_status_check_at": video.last_status_check_at,
        "created_at": video.created_at,
        "updated_at": video.updated_at,
        "completed_at": video.completed_at,
        "download_url": f"/api/v1/projects/{video.project_id}/videos/{video.id}/download" if has_download else None,
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


def get_video_size(resolution: str) -> str:
    normalized = resolution.lower().strip()
    if normalized == "720p":
        return "1280x720"
    return "1920x1080"


def get_media_duration_seconds(file_path: Path) -> float | None:
    ffprobe_binary = shutil.which("ffprobe")
    if not ffprobe_binary or not file_path.exists():
        return None

    command = [
        ffprobe_binary,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)
        duration = float(result.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None

    return duration if duration > 0 else None


def is_valid_mp4_file(file_path: Path) -> bool:
    if file_path.suffix.lower() != ".mp4" or not file_path.exists() or not file_path.is_file():
        return False
    if file_path.stat().st_size < 64:
        return False
    return b"ftyp" in file_path.read_bytes()[:64]


def get_video_generation_timeout(audio: GeneratedAudio | None) -> int:
    if audio and audio.duration_seconds:
        return max(60, int(audio.duration_seconds) + 90)
    return 300


def create_mock_video_file(
    video_dir: Path,
    project_id: UUID,
    resolution: str,
    audio: GeneratedAudio | None,
) -> tuple[str, Path, int, float | None]:
    ffmpeg_binary = shutil.which("ffmpeg")
    if not ffmpeg_binary:
        raise RuntimeError("ffmpeg is not available in the backend container.")
    if audio is None or not audio.file_path:
        raise RuntimeError("A source audio file is required to generate a mock video.")

    audio_path = Path(audio.file_path)
    if not audio_path.exists() or not audio_path.is_file():
        raise RuntimeError("Source audio file does not exist.")

    filename = f"{project_id}-mock-video-{uuid.uuid4().hex}.mp4"
    file_path = video_dir / filename
    video_filter = (
        f"color=c=#050505:s={get_video_size(resolution)}:r=30,"
        "drawtext=text='VVE Engine - Video mock':fontcolor=white:fontsize=56:x=(w-text_w)/2:y=(h-text_h)/2"
    )
    # -shortest alone can overshoot the audio by up to a couple of seconds
    # (encoder buffering on the infinite lavfi source), so pin the exact
    # duration with -t whenever ffprobe can read it from the source audio.
    source_audio_duration = get_media_duration_seconds(audio_path)
    duration_args = ["-t", f"{source_audio_duration:.3f}"] if source_audio_duration else []
    command_with_text = [
        ffmpeg_binary,
        "-y",
        "-f",
        "lavfi",
        "-i",
        video_filter,
        "-i",
        str(audio_path),
        "-shortest",
        *duration_args,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(file_path),
    ]
    fallback_command = [
        ffmpeg_binary,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=#050505:s={get_video_size(resolution)}:r=30",
        "-i",
        str(audio_path),
        "-shortest",
        *duration_args,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(file_path),
    ]
    timeout = get_video_generation_timeout(audio)

    try:
        subprocess.run(command_with_text, check=True, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        try:
            file_path.unlink(missing_ok=True)
            subprocess.run(fallback_command, check=True, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as fallback_exc:
            file_path.unlink(missing_ok=True)
            raise RuntimeError("Could not generate a valid MP4 mock video.") from fallback_exc

    if not is_valid_mp4_file(file_path):
        file_path.unlink(missing_ok=True)
        raise RuntimeError("Generated mock video is not a valid MP4 file.")

    duration = get_media_duration_seconds(file_path) or audio.duration_seconds
    return filename, file_path, file_path.stat().st_size, duration


def generate_video(
    db: Session,
    current_user: User,
    project_id: UUID,
    payload: GeneratedVideoGenerateRequest,
    settings: Settings | None = None,
) -> GeneratedVideo:
    active_settings = settings or get_settings()
    provider = (payload.provider or active_settings.video_provider or "mock").lower().strip()
    if provider == "heygen":
        return generate_heygen_video(db, current_user, project_id, payload, active_settings)
    if provider == "did":
        return generate_did_video(db, current_user, project_id, payload, active_settings)
    if provider == "sync":
        return generate_sync_video(db, current_user, project_id, payload, active_settings)
    return generate_mock_video(db, current_user, project_id, payload, active_settings)


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
    file_name: str | None = None
    file_path: Path | None = None
    file_size: int | None = None
    duration_seconds: float | None = None
    video_status = "completed"
    error_message: str | None = None

    try:
        file_name, file_path, file_size, duration_seconds = create_mock_video_file(video_dir, project.id, resolution, audio)
    except RuntimeError:
        video_status = "completed_mock"
        error_message = MOCK_VIDEO_UNAVAILABLE_MESSAGE

    now = datetime.now(UTC)

    video = GeneratedVideo(
        project_id=project.id,
        lesson_id=payload.lesson_id,
        module_id=payload.module_id,
        audio_id=audio.id if audio else None,
        avatar_id=payload.avatar_id,
        avatar_name=payload.avatar_name,
        provider=provider,
        status=video_status,
        resolution=resolution,
        format=video_format,
        file_path=str(file_path) if file_path else None,
        file_name=file_name,
        file_size_bytes=file_size,
        duration_seconds=int(round(duration_seconds)) if duration_seconds else None,
        error_message=error_message,
        extra_metadata={
            "mock": True,
            "mock_mp4_real": video_status == "completed",
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


def map_heygen_status(remote_status: str) -> str:
    mapping = {
        "pending": "pending",
        "waiting": "pending",
        "processing": "processing",
        "completed": "completed",
        "failed": "failed",
    }
    return mapping.get(remote_status, "processing")


def map_did_status(remote_status: str) -> str:
    mapping = {
        "created": "pending",
        "started": "processing",
        "done": "completed",
        "error": "failed",
        "rejected": "failed",
    }
    return mapping.get(remote_status, "processing")


def map_sync_status(remote_status: str) -> str:
    mapping = {
        "PENDING": "pending",
        "PROCESSING": "processing",
        "COMPLETED": "completed",
        "FAILED": "failed",
        "REJECTED": "failed",
    }
    return mapping.get(remote_status.upper(), "processing")


def get_heygen_avatar_id(payload: GeneratedVideoGenerateRequest, settings: Settings) -> str:
    avatar_id = (payload.avatar_id or "").strip() or (settings.heygen_default_avatar_id or "").strip()
    if not avatar_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe um avatar_id da HeyGen ou configure HEYGEN_DEFAULT_AVATAR_ID.",
        )
    return avatar_id


def generate_heygen_video(
    db: Session,
    current_user: User,
    project_id: UUID,
    payload: GeneratedVideoGenerateRequest,
    settings: Settings | None = None,
) -> GeneratedVideo:
    active_settings = settings or get_settings()
    if not active_settings.heygen_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HEYGEN_API_KEY não configurada no servidor.",
        )

    project = get_project_for_video(db, current_user, project_id)
    audio = get_audio_for_video(db, project.id, payload.audio_id)
    if audio is None or not audio.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selecione um áudio já gerado para criar o vídeo com a HeyGen.",
        )
    validate_lesson_for_video(db, current_user, project.id, payload.lesson_id)
    avatar_id = get_heygen_avatar_id(payload, active_settings)

    audio_path = Path(audio.file_path)
    if not audio_path.exists() or not audio_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo de áudio de origem não encontrado no storage.",
        )

    resolution = payload.resolution or active_settings.video_default_resolution or "1080p"

    try:
        asset = heygen.upload_audio_asset(audio_path, active_settings)
        job = heygen.create_heygen_video(
            avatar_id=avatar_id,
            audio_asset_id=asset.asset_id,
            resolution=resolution,
            settings=active_settings,
            title=f"VVE Engine - {audio.title}" if audio.title else None,
        )
    except heygen.HeyGenAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc

    now = datetime.now(UTC)
    video = GeneratedVideo(
        project_id=project.id,
        lesson_id=payload.lesson_id,
        module_id=payload.module_id,
        audio_id=audio.id,
        avatar_id=avatar_id,
        avatar_name=payload.avatar_name,
        provider="heygen",
        status=map_heygen_status(job.status),
        resolution=resolution,
        format="mp4",
        provider_job_id=job.video_id,
        remote_asset_id=asset.asset_id,
        last_status_check_at=now,
        provider_response=job.raw_response,
        extra_metadata={
            "audio_title": audio.title if audio else None,
            **(payload.extra_metadata or {}),
        },
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def build_public_audio_url(audio: GeneratedAudio, settings: Settings) -> str:
    token = generate_audio_asset_token(audio.id, settings=settings)
    base_url = (settings.public_base_url or "http://localhost:8000").rstrip("/")
    return f"{base_url}{settings.api_prefix}/public/audio-assets/{token}"


def generate_did_video(
    db: Session,
    current_user: User,
    project_id: UUID,
    payload: GeneratedVideoGenerateRequest,
    settings: Settings | None = None,
) -> GeneratedVideo:
    active_settings = settings or get_settings()
    if not active_settings.did_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DID_API_KEY não configurada no servidor.")

    project = get_project_for_video(db, current_user, project_id)
    audio = get_audio_for_video(db, project.id, payload.audio_id)
    if audio is None or not audio.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selecione um áudio já gerado para criar o vídeo com a D-ID.",
        )
    validate_lesson_for_video(db, current_user, project.id, payload.lesson_id)

    source_image_url = (payload.source_image_url or "").strip() or (
        active_settings.did_default_source_image_url or ""
    ).strip()
    if not source_image_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe source_image_url ou configure DID_DEFAULT_SOURCE_IMAGE_URL.",
        )

    audio_path = Path(audio.file_path)
    if not audio_path.exists() or not audio_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo de áudio de origem não encontrado no storage.",
        )

    try:
        asset = did.upload_audio_asset(audio_path, active_settings)
        job = did.create_talk(
            source_image_url=source_image_url,
            audio_url=asset.url,
            settings=active_settings,
            title=f"VVE Engine - {audio.title}" if audio.title else None,
        )
    except VideoProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc

    now = datetime.now(UTC)
    video = GeneratedVideo(
        project_id=project.id,
        lesson_id=payload.lesson_id,
        module_id=payload.module_id,
        audio_id=audio.id,
        avatar_id=payload.avatar_id,
        avatar_name=payload.avatar_name,
        provider="did",
        status=map_did_status(job.status),
        resolution=payload.resolution or active_settings.video_default_resolution or "1080p",
        format="mp4",
        provider_job_id=job.job_id,
        last_status_check_at=now,
        provider_response=job.raw_response,
        source_image_url=source_image_url,
        extra_metadata={
            "audio_title": audio.title if audio else None,
            **(payload.extra_metadata or {}),
        },
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def generate_sync_video(
    db: Session,
    current_user: User,
    project_id: UUID,
    payload: GeneratedVideoGenerateRequest,
    settings: Settings | None = None,
) -> GeneratedVideo:
    active_settings = settings or get_settings()
    if not active_settings.sync_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SYNC_API_KEY não configurada no servidor.")

    project = get_project_for_video(db, current_user, project_id)
    audio = get_audio_for_video(db, project.id, payload.audio_id)
    if audio is None or not audio.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selecione um áudio já gerado para criar o vídeo com a Sync Labs.",
        )
    validate_lesson_for_video(db, current_user, project.id, payload.lesson_id)

    source_video_url = (payload.source_video_url or "").strip() or (
        active_settings.sync_default_source_video_url or ""
    ).strip()
    source_image_url = (payload.source_image_url or "").strip() or (
        active_settings.sync_default_source_image_url or ""
    ).strip()
    if not source_video_url and not source_image_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Informe source_video_url ou source_image_url, ou configure "
                "SYNC_DEFAULT_SOURCE_VIDEO_URL/SYNC_DEFAULT_SOURCE_IMAGE_URL."
            ),
        )

    audio_path = Path(audio.file_path)
    if not audio_path.exists() or not audio_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo de áudio de origem não encontrado no storage.",
        )

    audio_url = build_public_audio_url(audio, active_settings)

    try:
        job = sync_provider.create_generation(
            audio_url=audio_url,
            settings=active_settings,
            source_video_url=source_video_url or None,
            source_image_url=source_image_url or None,
            model=payload.model,
        )
    except VideoProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc

    now = datetime.now(UTC)
    video = GeneratedVideo(
        project_id=project.id,
        lesson_id=payload.lesson_id,
        module_id=payload.module_id,
        audio_id=audio.id,
        avatar_id=payload.avatar_id,
        avatar_name=payload.avatar_name,
        provider="sync",
        status=map_sync_status(job.status),
        resolution=payload.resolution or active_settings.video_default_resolution or "1080p",
        format="mp4",
        provider_job_id=job.job_id,
        last_status_check_at=now,
        provider_response=job.raw_response,
        source_image_url=source_image_url or None,
        source_video_url=source_video_url or None,
        extra_metadata={
            "audio_title": audio.title if audio else None,
            "model": payload.model or active_settings.sync_default_model,
            **(payload.extra_metadata or {}),
        },
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def refresh_video_status(
    db: Session,
    current_user: User,
    project_id: UUID,
    video_id: UUID,
    settings: Settings | None = None,
) -> GeneratedVideo:
    active_settings = settings or get_settings()
    video = get_video_for_project(db, current_user, project_id, video_id)

    if video.provider not in {"heygen", "did", "sync"} or not video.provider_job_id:
        return video
    if video.status in {"completed", "failed"}:
        return video

    try:
        if video.provider == "heygen":
            remote = heygen.get_heygen_video_status(video.provider_job_id, active_settings)
            mapped_status = map_heygen_status(remote.status)
            download_fn = heygen.download_heygen_video
            provider_label = "HeyGen"
        elif video.provider == "did":
            remote = did.get_talk_status(video.provider_job_id, active_settings)
            mapped_status = map_did_status(remote.status)
            download_fn = did.download_video
            provider_label = "D-ID"
        else:
            remote = sync_provider.get_generation_status(video.provider_job_id, active_settings)
            mapped_status = map_sync_status(remote.status)
            download_fn = sync_provider.download_video
            provider_label = "Sync Labs"
    except (heygen.HeyGenAPIError, VideoProviderError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc

    video.status = mapped_status
    video.provider_response = remote.raw_response
    video.last_status_check_at = datetime.now(UTC)

    if mapped_status == "failed":
        video.error_message = remote.failure_message or f"Falha ao gerar vídeo na {provider_label}."
    elif mapped_status == "completed" and remote.video_url:
        video.remote_video_url = remote.video_url
        try:
            video_dir = get_video_storage_dir(active_settings)
            filename = f"{project_id}-{video.provider}-video-{uuid.uuid4().hex}.mp4"
            file_path = video_dir / filename
            download_fn(remote.video_url, file_path)
            if not is_valid_mp4_file(file_path):
                file_path.unlink(missing_ok=True)
                raise RuntimeError(f"Arquivo baixado da {provider_label} não é um MP4 válido.")
            video.file_path = str(file_path)
            video.file_name = filename
            video.file_size_bytes = file_path.stat().st_size
            duration = get_media_duration_seconds(file_path) or remote.duration
            video.duration_seconds = int(round(duration)) if duration else None
            video.completed_at = datetime.now(UTC)
        except (heygen.HeyGenAPIError, VideoProviderError, RuntimeError, OSError) as exc:
            video.error_message = f"Vídeo concluído na {provider_label}, mas falhou ao salvar localmente: {exc}"
    elif mapped_status == "completed" and not remote.video_url:
        video.error_message = f"{provider_label} marcou o vídeo como concluído, mas não retornou a URL final."

    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def get_video_download_path(db: Session, current_user: User, project_id: UUID, video_id: UUID) -> tuple[GeneratedVideo, Path]:
    video = get_video_for_project(db, current_user, project_id, video_id)
    if video.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=VIDEO_FILE_UNAVAILABLE_MESSAGE)
    if not video.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=VIDEO_FILE_UNAVAILABLE_MESSAGE)

    video_dir = get_video_storage_dir().resolve()
    file_path = Path(video.file_path).resolve()
    if video_dir not in file_path.parents:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Caminho de video invalido.")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=VIDEO_FILE_UNAVAILABLE_MESSAGE)
    if not is_valid_mp4_file(file_path):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=VIDEO_FILE_UNAVAILABLE_MESSAGE)

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
