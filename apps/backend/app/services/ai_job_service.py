from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.services.ai_orchestrator_service import generate_project_structure
from app.services.educational_content_service import generate_educational_content
from app.services.project_service import get_project_by_id


def create_ai_job(
    db: Session,
    current_user: User,
    project_id: UUID,
    job_type: str,
    generation_language: str = "pt-BR",
) -> ProcessingJob:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    job = ProcessingJob(
        project_id=project.id,
        organization_id=current_user.organization_id,
        job_type=job_type,
        status="pending",
        attempts=0,
        max_attempts=1,
        progress=0,
        current_step="Aguardando processamento",
        message="Processamento iniciado",
        payload_json={"generation_language": generation_language},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_project_job(db: Session, current_user: User, project_id: UUID, job_id: UUID) -> ProcessingJob:
    get_project_by_id(db, current_user.organization_id, project_id)
    job = db.execute(
        select(ProcessingJob).where(
            ProcessingJob.id == job_id,
            ProcessingJob.project_id == project_id,
            ProcessingJob.organization_id == current_user.organization_id,
        )
    ).scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job nao encontrado.",
        )

    return job


def mark_background_job_failed(db: Session, job: ProcessingJob, error_message: str) -> None:
    job.status = "failed"
    job.error_message = error_message
    job.message = "Falha no processamento"
    job.finished_at = datetime.now(UTC)
    db.commit()


def run_ai_structure_job(job_id: UUID, user_id: UUID, project_id: UUID, generation_language: str) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        user = db.get(User, user_id)
        if job is None or user is None:
            return

        try:
            generate_project_structure(db, user, project_id, generation_language, job=job)
        except Exception as exc:
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            if job is not None and job.status != "failed":
                mark_background_job_failed(db, job, str(exc))


def run_educational_content_job(job_id: UUID, user_id: UUID, project_id: UUID, generation_language: str) -> None:
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        user = db.get(User, user_id)
        if job is None or user is None:
            return

        try:
            generate_educational_content(db, user, project_id, generation_language, job=job)
        except Exception as exc:
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            if job is not None and job.status != "failed":
                mark_background_job_failed(db, job, str(exc))
