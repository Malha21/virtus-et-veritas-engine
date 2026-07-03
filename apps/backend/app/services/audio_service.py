import uuid
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.generated_audio import GeneratedAudio
from app.models.generated_content import GeneratedContent
from app.models.instructor_profile import InstructorProfile
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
SUPPORTED_VOICE_PROVIDERS = {"openai", "elevenlabs"}
ELEVENLABS_PROVIDER_ALIASES = {"elevenlabs", "eleven_labs", "eleven labs"}


@dataclass(frozen=True)
class VoiceSettings:
    provider: str
    voice: str
    model: str
    output_format: str
    personalized_voice_used: bool
    notice: str | None = None


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
        "voice_provider": audio.voice_provider,
        "voice": audio.voice,
        "model": audio.model,
        "format": audio.format,
        "personalized_voice_used": audio.personalized_voice_used,
        "voice_notice": audio.voice_notice,
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


def normalize_voice_provider(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in ELEVENLABS_PROVIDER_ALIASES:
        return "elevenlabs"
    return normalized


def get_instructor_profile_for_user(db: Session, current_user: User) -> InstructorProfile | None:
    return db.execute(
        select(InstructorProfile).where(InstructorProfile.user_id == current_user.id)
    ).scalar_one_or_none()


def resolve_voice_settings(
    db: Session,
    current_user: User,
    payload: AudioGenerateRequest,
    settings: Settings,
) -> VoiceSettings:
    default_voice = settings.openai_tts_voice
    model = payload.model or settings.openai_tts_model
    profile = get_instructor_profile_for_user(db, current_user)

    if profile is None:
        return VoiceSettings(
            provider="OpenAI",
            voice=default_voice,
            model=model,
            output_format=settings.openai_tts_format,
            personalized_voice_used=False,
            notice="Nenhum perfil de instrutor configurado. Foi usada a voz padrão do sistema.",
        )

    if not profile.consent_voice_clone:
        return VoiceSettings(
            provider="OpenAI",
            voice=default_voice,
            model=model,
            output_format=settings.openai_tts_format,
            personalized_voice_used=False,
            notice="A voz personalizada não foi usada porque o consentimento não está ativo.",
        )

    provider = (profile.voice_provider or "").strip()
    if not provider:
        return VoiceSettings(
            provider="OpenAI",
            voice=default_voice,
            model=model,
            output_format=settings.openai_tts_format,
            personalized_voice_used=False,
            notice="Perfil do instrutor sem provider de voz. Foi usada a voz padrão do sistema.",
        )

    normalized_provider = normalize_voice_provider(provider)
    if normalized_provider not in SUPPORTED_VOICE_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O provider de voz cadastrado ainda não está integrado nesta versão.",
        )

    if normalized_provider == "elevenlabs":
        if not profile.voice_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Voice ID da ElevenLabs não configurado no Perfil do Instrutor.",
            )
        return VoiceSettings(
            provider="ElevenLabs",
            voice=profile.voice_id.strip(),
            model=settings.elevenlabs_tts_model,
            output_format=settings.elevenlabs_output_format,
            personalized_voice_used=True,
            notice="Áudio gerado com a voz personalizada configurada no Perfil do Instrutor.",
        )

    voice = (profile.voice_id or profile.voice_name or default_voice).strip()
    personalized_voice_used = bool(profile.voice_id or profile.voice_name)
    notice = None
    if not personalized_voice_used:
        notice = "Perfil OpenAI sem voice_id ou voice_name. Foi usada a voz padrão do sistema."

    return VoiceSettings(
        provider="OpenAI",
        voice=voice,
        model=model,
        output_format=settings.openai_tts_format,
        personalized_voice_used=personalized_voice_used,
        notice=notice,
    )


def generate_openai_tts(text: str, voice_settings: VoiceSettings, audio_format: str, settings: Settings) -> bytes:
    if not settings.openai_api_key or settings.openai_api_key == "change_me_openai_api_key":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chave OpenAI não configurada no servidor.",
        )

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.audio.speech.create(
            model=voice_settings.model,
            voice=voice_settings.voice,
            input=text,
            response_format=audio_format,
        )
        return read_tts_response_bytes(response)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível gerar o áudio agora. Verifique a voz configurada e tente novamente.",
        ) from exc


def generate_elevenlabs_tts(text: str, voice_settings: VoiceSettings, settings: Settings) -> bytes:
    if not settings.elevenlabs_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chave ElevenLabs não configurada no servidor.",
        )
    if not voice_settings.voice:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voice ID da ElevenLabs não configurado no Perfil do Instrutor.",
        )

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_settings.voice}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": voice_settings.model,
    }
    params = {"output_format": voice_settings.output_format} if voice_settings.output_format else None

    try:
        response = httpx.post(url, headers=headers, json=payload, params=params, timeout=120)
        response.raise_for_status()
        return response.content
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível gerar o áudio com a ElevenLabs. Verifique o Voice ID e a configuração da conta.",
        ) from exc


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
    audio_format = (payload.format or active_settings.openai_tts_format or "mp3").lower()
    if audio_format not in ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de áudio inválido.",
        )

    voice_settings = resolve_voice_settings(db, current_user, payload, active_settings)
    stored_audio_format = "mp3" if voice_settings.provider == "ElevenLabs" else audio_format

    audio_dir = get_audio_storage_dir(active_settings)
    filename = f"{project.id}-{payload.block_index}-{uuid.uuid4().hex}.{stored_audio_format}"
    file_path = audio_dir / filename

    if voice_settings.provider == "ElevenLabs":
        audio_bytes = generate_elevenlabs_tts(text, voice_settings, active_settings)
    else:
        audio_bytes = generate_openai_tts(text, voice_settings, audio_format, active_settings)
    file_path.write_bytes(audio_bytes)

    audio = GeneratedAudio(
        project_id=project.id,
        generated_content_id=payload.generated_content_id,
        block_index=payload.block_index,
        title=payload.title,
        source_text=text,
        voice_provider=voice_settings.provider,
        voice=voice_settings.voice,
        model=voice_settings.model,
        format=stored_audio_format,
        file_path=str(file_path),
        personalized_voice_used=voice_settings.personalized_voice_used,
        voice_notice=voice_settings.notice,
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
