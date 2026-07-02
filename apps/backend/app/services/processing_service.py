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
from app.services.pdf_service import PDFTextExtractionError, extract_text_from_pdf
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


def get_latest_source_pdf(db: Session, project: Project) -> ProjectFile:
    source_pdf = db.execute(
        select(ProjectFile)
        .where(
            ProjectFile.project_id == project.id,
            ProjectFile.organization_id == project.organization_id,
            ProjectFile.file_type == "source_pdf",
            ProjectFile.status == "uploaded",
        )
        .order_by(ProjectFile.created_at.desc())
    ).scalars().first()

    if source_pdf is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Envie um PDF antes de iniciar o processamento.",
        )

    return source_pdf


def start_text_extraction(db: Session, current_user: User, project_id: UUID) -> ProcessingJob:
    settings = get_settings()
    project = get_project_by_id(db, current_user.organization_id, project_id)
    source_pdf = get_latest_source_pdf(db, project)

    job = ProcessingJob(
        project_id=project.id,
        organization_id=current_user.organization_id,
        job_type="extract_pdf_text",
        status="pending",
        attempts=0,
        max_attempts=3,
        payload_json={"project_file_id": str(source_pdf.id)},
    )
    db.add(job)
    db.flush()

    try:
        job.status = "running"
        job.attempts = 1
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
        extracted_text = extract_text_from_pdf(pdf_path)

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
        job.finished_at = datetime.now(UTC)
        add_processing_log(
            db,
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_id=job.id,
            level="error",
            message="Falha ao extrair texto do PDF",
            context_json={"error": str(exc)},
        )
        db.commit()
        db.refresh(job)
        return job


def get_processing_status(db: Session, current_user: User, project_id: UUID) -> dict[str, object]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    status_map = {
        "draft": (0, "Aguardando PDF"),
        "uploaded": (20, "Arquivo recebido"),
        "queued": (35, "Processamento na fila"),
        "extracting_text": (60, "Extraindo texto do PDF"),
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
    project = get_project_by_id(db, current_user.organization_id, project_id)
    statement = (
        select(ProcessingLog)
        .where(
            ProcessingLog.project_id == project.id,
            ProcessingLog.organization_id == current_user.organization_id,
        )
        .order_by(ProcessingLog.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())
