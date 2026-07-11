import re
import shutil
import subprocess
import time
import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.generated_audio import GeneratedAudio
from app.models.generated_content import GeneratedContent
from app.models.generated_video import GeneratedVideo
from app.models.project import Project
from app.models.user import User
from app.models.video_pipeline_job import VideoPipelineJob
from app.models.video_pipeline_job_item import VideoPipelineJobItem
from app.schemas.audio import AudioGenerateRequest
from app.schemas.video import GeneratedVideoGenerateRequest
from app.schemas.video_pipeline import VideoPipelineJobCreate
from app.services.audio_service import generate_tts_audio, get_audio_storage_dir
from app.services.educational_content_service import build_lesson_speech_text, get_content_metadata_number
from app.services.project_service import get_project_by_id
from app.services.video_avatar_service import get_active_avatar_for_generation
from app.services.video_service import generate_video, get_media_duration_seconds, refresh_video_status

TERMINAL_VIDEO_STATES = {"completed", "completed_mock", "failed"}
PIPELINE_AUDIO_MARKER = "[Pipeline]"
MAX_TTS_CHUNK_CHARS = 4500
POLL_INTERVAL_SECONDS = 8
POLL_MAX_ATTEMPTS = 45


def get_lesson_scripts_for_project(db: Session, project: Project) -> list[GeneratedContent]:
    contents = list(
        db.execute(
            select(GeneratedContent).where(
                GeneratedContent.project_id == project.id,
                GeneratedContent.organization_id == project.organization_id,
                GeneratedContent.content_type == "lesson_script",
            )
        )
        .scalars()
        .all()
    )
    contents.sort(
        key=lambda content: (
            get_content_metadata_number(content, "module_number"),
            get_content_metadata_number(content, "lesson_number"),
            content.created_at,
        )
    )
    return contents


def resolve_target_lessons(
    db: Session, project: Project, payload: VideoPipelineJobCreate
) -> list[GeneratedContent]:
    all_lessons = get_lesson_scripts_for_project(db, project)

    if payload.scope == "course":
        if not all_lessons:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum roteiro de aula encontrado.")
        return all_lessons

    if payload.scope == "module":
        selected = [
            content
            for content in all_lessons
            if get_content_metadata_number(content, "module_number") == payload.module_index
        ]
        if not selected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Nenhuma aula encontrada para o módulo {payload.module_index}.",
            )
        return selected

    lesson = next((content for content in all_lessons if content.id == payload.lesson_id), None)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aula não encontrada.")
    return [lesson]


def get_lesson_script_dict(lesson: GeneratedContent) -> dict:
    content_json = lesson.content_json or {}
    script = content_json.get("lesson_script")
    return script if isinstance(script, dict) else {}


def build_lesson_base_title(script: dict, lesson: GeneratedContent) -> str:
    module_number = script.get("module_number")
    lesson_number = script.get("lesson_number")
    lesson_title = script.get("lesson_title") or lesson.title or "Aula"
    module_label = f"Módulo {module_number}" if module_number else "Módulo"
    lesson_label = f"Aula {lesson_number}" if lesson_number else "Aula"
    return f"{module_label} - {lesson_label}: {lesson_title}"


def get_lesson_narration_text(script: dict) -> str:
    text = script.get("narration_text") or script.get("script_text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return build_lesson_speech_text(script).strip()


def split_text_into_chunks(text: str, max_len: int = MAX_TTS_CHUNK_CHARS) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_len:
        return [cleaned]

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", cleaned) if part.strip()]
    if len(paragraphs) <= 1:
        paragraphs = re.findall(r"[^.!?]+[.!?]+|[^.!?]+$", cleaned) or [cleaned]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_len:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= max_len:
            current = paragraph
        else:
            for start in range(0, len(paragraph), max_len):
                chunks.append(paragraph[start : start + max_len])
            current = ""
    if current:
        chunks.append(current)
    return chunks


def find_existing_pipeline_audio(db: Session, project_id: UUID, lesson_id: UUID) -> GeneratedAudio | None:
    return db.execute(
        select(GeneratedAudio)
        .where(
            GeneratedAudio.project_id == project_id,
            GeneratedAudio.generated_content_id == lesson_id,
            GeneratedAudio.title.ilike(f"%Consolidado {PIPELINE_AUDIO_MARKER}"),
        )
        .order_by(GeneratedAudio.created_at.desc())
    ).scalars().first()


def concatenate_audio_files(
    project: Project,
    base_title: str,
    lesson: GeneratedContent,
    narration_text: str,
    block_audios: list[GeneratedAudio],
) -> GeneratedAudio:
    ffmpeg_binary = shutil.which("ffmpeg")
    if not ffmpeg_binary:
        raise RuntimeError("ffmpeg não está disponível no servidor para consolidar os blocos de áudio.")

    audio_dir = get_audio_storage_dir()
    filelist_path = audio_dir / f"concat-{uuid.uuid4().hex}.txt"
    output_filename = f"{project.id}-consolidated-{uuid.uuid4().hex}.mp3"
    output_path = audio_dir / output_filename

    try:
        lines = [f"file '{block.file_path}'" for block in block_audios]
        filelist_path.write_text("\n".join(lines), encoding="utf-8")

        command = [
            ffmpeg_binary,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(filelist_path),
            "-c",
            "copy",
            str(output_path),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        output_path.unlink(missing_ok=True)
        raise RuntimeError("Não foi possível consolidar os blocos de áudio da aula.") from exc
    finally:
        filelist_path.unlink(missing_ok=True)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Falha ao gerar o arquivo de áudio consolidado da aula.")

    duration = get_media_duration_seconds(output_path)
    last_block = block_audios[-1]

    consolidated = GeneratedAudio(
        project_id=project.id,
        generated_content_id=lesson.id,
        block_index=0,
        title=f"{base_title} - Consolidado {PIPELINE_AUDIO_MARKER}",
        source_text=narration_text,
        voice_provider=last_block.voice_provider,
        voice=last_block.voice,
        model=last_block.model,
        format="mp3",
        file_path=str(output_path),
        duration_seconds=duration,
        personalized_voice_used=last_block.personalized_voice_used,
        voice_notice=last_block.voice_notice,
        status="completed",
    )
    return consolidated


def resolve_or_generate_audio(
    db: Session,
    current_user: User,
    project: Project,
    job: VideoPipelineJob,
    lesson: GeneratedContent,
) -> GeneratedAudio:
    if not job.force_regenerate_audio and job.skip_existing_audio:
        existing = find_existing_pipeline_audio(db, project.id, lesson.id)
        if existing is not None:
            return existing

    script = get_lesson_script_dict(lesson)
    base_title = build_lesson_base_title(script, lesson)
    narration_text = get_lesson_narration_text(script)
    if not narration_text:
        raise RuntimeError("O roteiro desta aula não possui texto de narração.")

    chunks = split_text_into_chunks(narration_text)
    if len(chunks) == 1:
        payload = AudioGenerateRequest(
            generated_content_id=lesson.id,
            block_index=1,
            title=f"{base_title} - Consolidado {PIPELINE_AUDIO_MARKER}",
            text=chunks[0],
            format="mp3",
        )
        return generate_tts_audio(db, current_user, project.id, payload)

    block_audios: list[GeneratedAudio] = []
    for index, chunk in enumerate(chunks, start=1):
        payload = AudioGenerateRequest(
            generated_content_id=lesson.id,
            block_index=index,
            title=f"{base_title} - Bloco {index} {PIPELINE_AUDIO_MARKER}",
            text=chunk,
            format="mp3",
        )
        block_audios.append(generate_tts_audio(db, current_user, project.id, payload))

    return concatenate_audio_files(project, base_title, lesson, narration_text, block_audios)


def poll_video_to_terminal_state(
    db: Session, current_user: User, project_id: UUID, video: GeneratedVideo
) -> GeneratedVideo:
    attempts = 0
    while video.status not in TERMINAL_VIDEO_STATES and attempts < POLL_MAX_ATTEMPTS:
        time.sleep(POLL_INTERVAL_SECONDS)
        video = refresh_video_status(db, current_user, project_id, video.id)
        attempts += 1
    return video


def find_existing_video(db: Session, project_id: UUID, lesson_id: UUID) -> GeneratedVideo | None:
    return db.execute(
        select(GeneratedVideo)
        .where(
            GeneratedVideo.project_id == project_id,
            GeneratedVideo.lesson_id == lesson_id,
            GeneratedVideo.status != "failed",
        )
        .order_by(GeneratedVideo.created_at.desc())
    ).scalars().first()


def resolve_or_generate_video(
    db: Session,
    current_user: User,
    project: Project,
    job: VideoPipelineJob,
    lesson: GeneratedContent,
    audio: GeneratedAudio,
) -> GeneratedVideo:
    if not job.force_regenerate_video and job.skip_existing_video:
        existing = find_existing_video(db, project.id, lesson.id)
        if existing is not None:
            if existing.status in TERMINAL_VIDEO_STATES:
                return existing
            return poll_video_to_terminal_state(db, current_user, project.id, existing)

    payload = GeneratedVideoGenerateRequest(
        lesson_id=lesson.id,
        audio_id=audio.id,
        video_avatar_id=job.video_avatar_id,
        provider=job.provider,
    )
    video = generate_video(db, current_user, project.id, payload)
    if video.status not in TERMINAL_VIDEO_STATES:
        video = poll_video_to_terminal_state(db, current_user, project.id, video)
    return video


def process_pipeline_item(
    db: Session,
    current_user: User,
    project: Project,
    job: VideoPipelineJob,
    item: VideoPipelineJobItem,
) -> None:
    lesson = db.get(GeneratedContent, item.lesson_content_id) if item.lesson_content_id else None
    if lesson is None:
        raise RuntimeError("Roteiro da aula não encontrado.")

    item.status = "generating_audio"
    item.started_at = item.started_at or datetime.now(UTC)
    db.add(item)
    db.commit()

    audio = resolve_or_generate_audio(db, current_user, project, job, lesson)
    item.generated_audio_id = audio.id
    item.status = "audio_completed"
    db.add(item)
    db.commit()

    item.status = "generating_video"
    db.add(item)
    db.commit()

    video = resolve_or_generate_video(db, current_user, project, job, lesson, audio)
    item.generated_video_id = video.id

    if video.status == "failed":
        raise RuntimeError(video.error_message or "Falha ao gerar o vídeo desta aula.")

    if video.status in TERMINAL_VIDEO_STATES:
        item.status = "completed"
        item.completed_at = datetime.now(UTC)
    else:
        item.status = "video_processing"
    db.add(item)
    db.commit()


def error_message_from_exception(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc) or "Falha desconhecida ao processar esta aula."


def finalize_job(db: Session, job: VideoPipelineJob) -> None:
    db.refresh(job)
    if job.status == "cancelled":
        remaining = db.execute(
            select(VideoPipelineJobItem).where(
                VideoPipelineJobItem.job_id == job.id,
                VideoPipelineJobItem.status == "pending",
            )
        ).scalars().all()
        for item in remaining:
            item.status = "skipped"
            db.add(item)
        job.completed_at = datetime.now(UTC)
        db.add(job)
        db.commit()
        return

    finished_items = job.completed_items + job.failed_items
    if finished_items < job.total_items:
        job.status = "partially_completed"
    elif job.failed_items == 0:
        job.status = "completed"
    elif job.completed_items > 0:
        job.status = "partially_completed"
    else:
        job.status = "failed"
    job.completed_at = datetime.now(UTC)
    job.current_item_label = None
    db.add(job)
    db.commit()


def run_pipeline(db: Session, current_user: User, job: VideoPipelineJob) -> None:
    if job.status not in {"pending", "failed", "partially_completed"}:
        return

    project = get_project_by_id(db, current_user.organization_id, job.project_id)
    job.status = "running"
    job.started_at = job.started_at or datetime.now(UTC)
    job.error_message = None
    db.add(job)
    db.commit()

    items = list(
        db.execute(
            select(VideoPipelineJobItem)
            .where(VideoPipelineJobItem.job_id == job.id)
            .order_by(
                VideoPipelineJobItem.module_index.asc(),
                VideoPipelineJobItem.lesson_index.asc(),
                VideoPipelineJobItem.created_at.asc(),
            )
        )
        .scalars()
        .all()
    )

    for item in items:
        db.refresh(job)
        if job.status == "cancelled":
            break
        if item.status != "pending":
            continue

        job.current_item_label = item.lesson_title
        db.add(job)
        db.commit()

        try:
            process_pipeline_item(db, current_user, project, job, item)
        except Exception as exc:  # noqa: BLE001 - per-item failures must not abort the whole job
            db.rollback()
            item = db.get(VideoPipelineJobItem, item.id)
            job = db.get(VideoPipelineJob, job.id)
            if item is not None and job is not None:
                item.status = "failed"
                item.error_message = error_message_from_exception(exc)[:2000]
                item.completed_at = datetime.now(UTC)
                job.failed_items += 1
                db.add(item)
                db.add(job)
                db.commit()
        else:
            if item.status == "completed":
                job.completed_items += 1
                db.add(job)
                db.commit()

    finalize_job(db, job)


def run_video_pipeline_job(job_id: UUID, user_id: UUID, project_id: UUID) -> None:
    with SessionLocal() as db:
        job = db.get(VideoPipelineJob, job_id)
        user = db.get(User, user_id)
        if job is None or user is None:
            return
        try:
            run_pipeline(db, user, job)
        except Exception as exc:  # noqa: BLE001 - top-level safety net for the background task
            db.rollback()
            job = db.get(VideoPipelineJob, job_id)
            if job is not None and job.status not in {"completed", "failed", "cancelled", "partially_completed"}:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                job.completed_at = datetime.now(UTC)
                db.add(job)
                db.commit()


def create_pipeline_job(
    db: Session, current_user: User, project_id: UUID, payload: VideoPipelineJobCreate
) -> VideoPipelineJob:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    lessons = resolve_target_lessons(db, project, payload)

    if payload.video_avatar_id:
        get_active_avatar_for_generation(db, project.id, payload.video_avatar_id)

    job = VideoPipelineJob(
        project_id=project.id,
        scope=payload.scope,
        module_index=payload.module_index,
        lesson_id=payload.lesson_id,
        lesson_index=get_content_metadata_number(lessons[0], "lesson_number") if payload.scope == "lesson" else None,
        status="pending",
        total_items=len(lessons),
        provider=payload.provider.lower().strip() if payload.provider else None,
        video_avatar_id=payload.video_avatar_id,
        skip_existing_audio=payload.skip_existing_audio,
        skip_existing_video=payload.skip_existing_video,
        force_regenerate_audio=payload.force_regenerate_audio,
        force_regenerate_video=payload.force_regenerate_video,
    )
    db.add(job)
    db.flush()

    for lesson in lessons:
        script = get_lesson_script_dict(lesson)
        item = VideoPipelineJobItem(
            job_id=job.id,
            project_id=project.id,
            lesson_content_id=lesson.id,
            module_index=get_content_metadata_number(lesson, "module_number"),
            lesson_index=get_content_metadata_number(lesson, "lesson_number"),
            lesson_title=build_lesson_base_title(script, lesson),
            status="pending",
        )
        db.add(item)

    db.commit()
    db.refresh(job)
    return job


def get_pipeline_job_for_project(db: Session, project_id: UUID, job_id: UUID) -> VideoPipelineJob:
    job = db.execute(
        select(VideoPipelineJob).where(
            VideoPipelineJob.id == job_id,
            VideoPipelineJob.project_id == project_id,
        )
    ).scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline não encontrado.")

    return job


def list_pipeline_jobs_for_project(db: Session, current_user: User, project_id: UUID) -> list[VideoPipelineJob]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    return list(
        db.execute(
            select(VideoPipelineJob)
            .where(VideoPipelineJob.project_id == project.id)
            .order_by(VideoPipelineJob.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_pipeline_job_items(db: Session, job_id: UUID) -> list[VideoPipelineJobItem]:
    return list(
        db.execute(
            select(VideoPipelineJobItem)
            .where(VideoPipelineJobItem.job_id == job_id)
            .order_by(
                VideoPipelineJobItem.module_index.asc(),
                VideoPipelineJobItem.lesson_index.asc(),
                VideoPipelineJobItem.created_at.asc(),
            )
        )
        .scalars()
        .all()
    )


def get_pipeline_job_detail(
    db: Session, current_user: User, project_id: UUID, job_id: UUID
) -> tuple[VideoPipelineJob, list[VideoPipelineJobItem]]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    job = get_pipeline_job_for_project(db, project.id, job_id)
    items = get_pipeline_job_items(db, job.id)
    return job, items


def start_pipeline_job(db: Session, current_user: User, project_id: UUID, job_id: UUID) -> VideoPipelineJob:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    job = get_pipeline_job_for_project(db, project.id, job_id)
    if job.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este pipeline já foi iniciado.")
    return job


def prepare_retry_failed(db: Session, current_user: User, project_id: UUID, job_id: UUID) -> VideoPipelineJob:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    job = get_pipeline_job_for_project(db, project.id, job_id)
    if job.status not in {"failed", "partially_completed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Somente pipelines com falhas podem ser reprocessados.",
        )

    failed_items = list(
        db.execute(
            select(VideoPipelineJobItem).where(
                VideoPipelineJobItem.job_id == job.id,
                VideoPipelineJobItem.status == "failed",
            )
        )
        .scalars()
        .all()
    )
    if not failed_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum item com falha para reprocessar.")

    for item in failed_items:
        item.status = "pending"
        item.error_message = None
        item.started_at = None
        item.completed_at = None
        db.add(item)

    job.status = "pending"
    job.failed_items = 0
    job.error_message = None
    job.completed_at = None
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def cancel_pipeline_job(db: Session, current_user: User, project_id: UUID, job_id: UUID) -> VideoPipelineJob:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    job = get_pipeline_job_for_project(db, project.id, job_id)
    if job.status in {"completed", "failed", "cancelled", "partially_completed"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este pipeline já foi finalizado.")

    job.status = "cancelled"
    if job.started_at is None:
        job.completed_at = datetime.now(UTC)
        items = list(
            db.execute(
                select(VideoPipelineJobItem).where(
                    VideoPipelineJobItem.job_id == job.id,
                    VideoPipelineJobItem.status == "pending",
                )
            )
            .scalars()
            .all()
        )
        for item in items:
            item.status = "skipped"
            db.add(item)

    db.add(job)
    db.commit()
    db.refresh(job)
    return job
