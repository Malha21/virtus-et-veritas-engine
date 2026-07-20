from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.ai import GenerateStructureRequest
from app.schemas.educational_content import GenerateEducationalContentRequest
from app.schemas.processing import ProcessingJobResponse, StartAIJobResponse
from app.services.ai_job_service import (
    create_ai_job,
    get_project_job,
    run_ai_structure_job,
    run_educational_content_from_coverage_plan_job,
    run_educational_content_job,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["jobs"])


@router.post("/ai-structure/jobs")
def start_ai_structure_job(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: GenerateStructureRequest | None = None,
) -> dict[str, object]:
    generation_language = payload.generation_language if payload else "pt-BR"
    job = create_ai_job(db, current_user, project_id, "generate_course_structure", generation_language)
    if job.status == "pending":
        background_tasks.add_task(run_ai_structure_job, job.id, current_user.id, project_id, generation_language)
    data = StartAIJobResponse(job_id=job.id, status=job.status, message="Processamento iniciado")
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/educational-content/jobs")
def start_educational_content_job(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: GenerateEducationalContentRequest | None = None,
) -> dict[str, object]:
    generation_language = payload.generation_language if payload else "pt-BR"
    job = create_ai_job(db, current_user, project_id, "generate_educational_content", generation_language)
    if job.status == "pending":
        background_tasks.add_task(run_educational_content_job, job.id, current_user.id, project_id, generation_language)
    data = StartAIJobResponse(job_id=job.id, status=job.status, message="Processamento iniciado")
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/coverage-plan-content/jobs")
def start_educational_content_from_coverage_plan_job(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: GenerateEducationalContentRequest | None = None,
) -> dict[str, object]:
    generation_language = payload.generation_language if payload else "pt-BR"
    job = create_ai_job(db, current_user, project_id, "generate_educational_content_from_coverage_plan", generation_language)
    if job.status == "pending":
        background_tasks.add_task(
            run_educational_content_from_coverage_plan_job, job.id, current_user.id, project_id, generation_language
        )
    data = StartAIJobResponse(job_id=job.id, status=job.status, message="Processamento iniciado")
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/jobs/{job_id}")
def get_job(
    project_id: UUID,
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    job = get_project_job(db, current_user, project_id, job_id)
    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}
