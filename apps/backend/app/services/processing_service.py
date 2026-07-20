from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.processing_job import ProcessingJob
from app.models.processing_log import ProcessingLog
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User
from app.services.pdf_service import PDFTextExtractionError, extract_text_from_epub, extract_text_from_pdf
from app.services.project_service import get_project_by_id


def add_processing_log(
    db: Session,
    project_id: UUID | None,
    organization_id: UUID | None,
    message: str,
    level: str = "info",
    job_id: UUID | None = None,
    context_json: dict | None = None,
) -> ProcessingLog:
    log = ProcessingLog(
        project_id=project_id,
        job_id=job_id,
        organization_id=organization_id,
        level=level,
        message=message,
        context_json=context_json or {},
    )
    db.add(log)
    db.flush()
    return log


STALE_JOB_THRESHOLD_MINUTES = 20


def reap_if_stale(db: Session, job: ProcessingJob | None) -> ProcessingJob | None:
    """Marca como falho e "descarta" um job "ativo" que na verdade morreu.

    Jobs rodam via FastAPI BackgroundTasks dentro do processo do backend: se o
    processo reinicia (deploy, crash) enquanto um job esta em pending/processing,
    a tarefa em background e perdida silenciosamente e o job fica preso nesse
    status para sempre - bloqueando qualquer nova tentativa do usuario, ja que
    o restante do sistema trata "existe job ativo" como "nao criar outro".
    Se o job nao for atualizado ha mais de STALE_JOB_THRESHOLD_MINUTES, tratamos
    como morto: marcamos failed com uma mensagem clara e liberamos o caminho
    para uma nova tentativa, em vez de deixar o usuario travado indefinidamente.
    """
    if job is None:
        return None

    updated_at = job.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)

    age_minutes = (datetime.now(UTC) - updated_at).total_seconds() / 60
    if age_minutes < STALE_JOB_THRESHOLD_MINUTES:
        return job

    job.status = "failed"
    job.error_message = (
        "Job interrompido (processo reiniciado durante a execução) e marcado como falho "
        "automaticamente. Tente novamente."
    )
    job.message = "Falha: job interrompido"
    job.finished_at = datetime.now(UTC)
    db.add(job)
    db.commit()
    return None


def update_processing_job(
    db: Session,
    job: ProcessingJob,
    progress: int,
    current_step: str,
    message: str | None = None,
) -> None:
    job.progress = max(job.progress or 0, max(0, min(progress, 100)))
    job.current_step = current_step
    job.message = message or current_step
    db.add(job)
    db.commit()


SOURCE_FILE_TYPES = ("source_pdf", "source_epub")


def get_latest_source_pdf(db: Session, project: Project) -> ProjectFile:
    source_file = db.execute(
        select(ProjectFile)
        .where(
            ProjectFile.project_id == project.id,
            ProjectFile.organization_id == project.organization_id,
            ProjectFile.file_type.in_(SOURCE_FILE_TYPES),
            ProjectFile.status == "uploaded",
        )
        .order_by(ProjectFile.created_at.desc())
    ).scalars().first()

    if source_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Envie um PDF ou EPUB antes de iniciar o processamento.",
        )

    return source_file


def start_text_extraction(db: Session, current_user: User, project_id: UUID) -> ProcessingJob:
    settings = get_settings()
    project = get_project_by_id(db, current_user, project_id)
    source_pdf = get_latest_source_pdf(db, project)
    is_epub = source_pdf.file_type == "source_epub"

    job = ProcessingJob(
        project_id=project.id,
        organization_id=current_user.organization_id,
        job_type="extract_pdf_text",
        status="pending",
        attempts=0,
        max_attempts=3,
        progress=0,
        current_step="Aguardando extracao",
        message="Processamento do documento criado",
        payload_json={"project_file_id": str(source_pdf.id)},
    )
    db.add(job)
    db.flush()

    try:
        job.status = "running"
        job.attempts = 1
        update_processing_job(db, job, 10, "Extraindo texto do documento", "Extracao de texto iniciada")
        job.started_at = datetime.now(UTC)
        project.processing_status = "extracting_text"
        add_processing_log(
            db,
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_id=job.id,
            message="Extração de texto iniciada",
        )
        db.flush()

        storage_root = Path(settings.storage_path)
        pdf_path = storage_root / source_pdf.storage_path
        extracted_text = extract_text_from_epub(pdf_path) if is_epub else extract_text_from_pdf(pdf_path)

        relative_text_path = Path(
            "organizations",
            str(current_user.organization_id),
            "projects",
            str(project.id),
            "extracted",
            "extracted_text.txt",
        )
        text_path = storage_root / relative_text_path
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(extracted_text, encoding="utf-8")

        source_pdf.extracted_text_path = relative_text_path.as_posix()
        project.processing_status = "text_extracted"
        job.status = "completed"
        update_processing_job(db, job, 100, "Texto extraido", "Texto extraido com sucesso")
        job.finished_at = datetime.now(UTC)
        job.result_json = {
            "project_file_id": str(source_pdf.id),
            "extracted_text_path": source_pdf.extracted_text_path,
            "character_count": len(extracted_text),
        }
        add_processing_log(
            db,
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_id=job.id,
            message="Texto extraído com sucesso",
            context_json={"character_count": len(extracted_text)},
        )
        db.commit()
        db.refresh(job)
        return job
    except (PDFTextExtractionError, Exception) as exc:
        project.processing_status = "failed"
        job.status = "failed"
        job.error_message = str(exc)
        job.message = "Falha ao extrair texto do documento"
        job.finished_at = datetime.now(UTC)
        add_processing_log(
            db,
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_id=job.id,
            level="error",
            message="Falha ao extrair texto do documento",
            context_json={"error": str(exc)},
        )
        db.commit()
        db.refresh(job)
        return job


def get_processing_status(db: Session, current_user: User, project_id: UUID) -> dict[str, object]:
    project = get_project_by_id(db, current_user, project_id)
    status_map = {
        "draft": (0, "Aguardando documento"),
        "uploaded": (20, "Arquivo recebido"),
        "queued": (35, "Processamento na fila"),
        "extracting_text": (60, "Extraindo texto do documento"),
        "text_extracted": (100, "Texto extraído com sucesso"),
        "ai_generating_structure": (85, "Gerando estrutura com IA"),
        "ai_structure_generated": (100, "Estrutura gerada com IA"),
        "ai_generating_educational_content": (90, "Gerando conteudos educacionais"),
        "educational_content_generated": (100, "Conteudos educacionais gerados"),
        "failed": (100, "Processamento falhou"),
    }
    progress, current_step = status_map.get(project.processing_status, (0, "Status em preparação"))
    return {
        "project_id": project.id,
        "processing_status": project.processing_status,
        "progress": progress,
        "current_step": current_step,
        "updated_at": project.updated_at,
    }


def list_processing_logs(db: Session, current_user: User, project_id: UUID) -> list[ProcessingLog]:
    project = get_project_by_id(db, current_user, project_id)
    statement = (
        select(ProcessingLog)
        .where(
            ProcessingLog.project_id == project.id,
            ProcessingLog.organization_id == current_user.organization_id,
        )
        .order_by(ProcessingLog.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())
