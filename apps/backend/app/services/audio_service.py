import uuid
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.generated_audio import GeneratedAudio
from app.models.generated_content import GeneratedContent
from app.models.project import Project
from app.models.user import User
from app.schemas.audio import AudioGenerateRequest

MAX_TTS_TEXT_LENGTH = 5000
ALLOWED_AUDIO_FORMATS = {"mp3", "wav", "aac", "flac", "opus", "pcm"}
MEDIA_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "opus": "audio/ogg",
    "pcm": "application/octet-stream",
}


def get_audio_storage_dir(settings: Settings | None = None) -> Path:
    active_settings = settings or get_settings()
    path = Path(active_settings.storage_path) / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_audio_media_type(audio_format: str) -> str:
    return MEDIA_TYPES.get(audio_format.lower(), "application/octet-stream")


def get_project_for_audio(db: Session, current_user: User, project_id: UUID) -> Project:
    project = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
            Project.archived_at.is_(None),
            Project.deleted_at.is_(None),
        )
    ).scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projeto não encontrado.",
        )

    return project


def get_audio_for_project(db: Session, current_user: User, project_id: UUID, audio_id: UUID) -> GeneratedAudio:
    get_project_for_audio(db, current_user, project_id)
    audio = db.execute(
        select(GeneratedAudio).where(
            GeneratedAudio.id == audio_id,
            GeneratedAudio.project_id == project_id,
        )
    ).scalar_one_or_none()

    if audio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Áudio não encontrado.",
        )

    return audio


def validate_generated_content(db: Session, current_user: User, project_id: UUID, generated_content_id: UUID | None) -> None:
    if generated_content_id is None:
        return

    exists = db.execute(
        select(GeneratedContent.id).where(
            GeneratedContent.id == generated_content_id,
            GeneratedContent.project_id == project_id,
            GeneratedContent.organization_id == current_user.organization_id,
        )
    ).scalar_one_or_none()

    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roteiro de origem não encontrado.",
        )


def audio_to_response_data(audio: GeneratedAudio) -> dict[str, object]:
    return {
        "id": audio.id,
        "project_id": audio.project_id,
        "generated_content_id": audio.generated_content_id,
        "block_index": audio.block_index,
        "title": audio.title,
        "voice": audio.voice,
        "model": audio.model,
        "format": audio.format,
        "duration_seconds": audio.duration_seconds,
        "status": audio.status,
        "created_at": audio.created_at,
        "download_url": f"/api/v1/projects/{audio.project_id}/audio/{audio.id}/download",
    }


def read_tts_response_bytes(response: object) -> bytes:
    if hasattr(response, "read"):
        data = response.read()
        if isinstance(data, bytes):
            return data

    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content

    if isinstance(response, bytes):
        return response

    raise RuntimeError("Resposta de áudio inválida retornada pelo provedor.")


def generate_tts_audio(
    db: Session,
    current_user: User,
    project_id: UUID,
    payload: AudioGenerateRequest,
    settings: Settings | None = None,
) -> GeneratedAudio:
    active_settings = settings or get_settings()
    project = get_project_for_audio(db, current_user, project_id)
    validate_generated_content(db, current_user, project.id, payload.generated_content_id)

    text = payload.text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Texto do bloco de narração não informado.",
        )
    if len(text) > MAX_TTS_TEXT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Texto do bloco excede o limite de {MAX_TTS_TEXT_LENGTH} caracteres.",
        )
    if not active_settings.openai_api_key or active_settings.openai_api_key == "change_me_openai_api_key":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OPENAI_API_KEY não configurada para geração de áudio.",
        )

    audio_format = (payload.format or active_settings.openai_tts_format or "mp3").lower()
    if audio_format not in ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de áudio inválido.",
        )

    model = payload.model or active_settings.openai_tts_model
    voice = payload.voice or active_settings.openai_tts_voice
    audio_dir = get_audio_storage_dir(active_settings)
    filename = f"{project.id}-{payload.block_index}-{uuid.uuid4().hex}.{audio_format}"
    file_path = audio_dir / filename

    try:
        client = OpenAI(api_key=active_settings.openai_api_key)
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format=audio_format,
        )
        audio_bytes = read_tts_response_bytes(response)
        file_path.write_bytes(audio_bytes)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Não foi possível gerar o áudio agora: {exc}",
        ) from exc

    audio = GeneratedAudio(
        project_id=project.id,
        generated_content_id=payload.generated_content_id,
        block_index=payload.block_index,
        title=payload.title,
        source_text=text,
        voice=voice,
        model=model,
        format=audio_format,
        file_path=str(file_path),
        status="completed",
    )
    db.add(audio)
    db.commit()
    db.refresh(audio)
    return audio


def list_project_audios(db: Session, current_user: User, project_id: UUID) -> list[GeneratedAudio]:
    get_project_for_audio(db, current_user, project_id)
    return list(
        db.execute(
            select(GeneratedAudio)
            .where(GeneratedAudio.project_id == project_id)
            .order_by(GeneratedAudio.block_index.asc(), GeneratedAudio.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_audio_download_path(db: Session, current_user: User, project_id: UUID, audio_id: UUID) -> tuple[GeneratedAudio, Path]:
    audio = get_audio_for_project(db, current_user, project_id, audio_id)
    audio_dir = get_audio_storage_dir().resolve()
    file_path = Path(audio.file_path).resolve()

    if audio_dir not in file_path.parents:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caminho de áudio inválido.",
        )
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo de áudio não encontrado.",
        )

    return audio, file_path


def delete_project_audio(db: Session, current_user: User, project_id: UUID, audio_id: UUID) -> None:
    audio = get_audio_for_project(db, current_user, project_id, audio_id)
    audio_dir = get_audio_storage_dir().resolve()
    file_path = Path(audio.file_path).resolve()

    if audio_dir not in file_path.parents:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caminho de áudio inválido.",
        )

    if file_path.exists() and file_path.is_file():
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass

    db.delete(audio)
    db.commit()
