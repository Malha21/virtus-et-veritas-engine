from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.video_pipeline_job import VideoPipelineJob
from app.models.video_pipeline_job_item import VideoPipelineJobItem
from app.schemas.video_pipeline import (
    VideoPipelineJobCreate,
    VideoPipelineJobItemRead,
    VideoPipelineJobRead,
)
from app.services.video_pipeline_service import (
    cancel_pipeline_job,
    create_pipeline_job,
    get_pipeline_job_detail,
    list_pipeline_jobs_for_project,
    prepare_retry_failed,
    run_video_pipeline_job,
    start_pipeline_job,
)

router = APIRouter(prefix="/projects/{project_id}/video-pipeline", tags=["video-pipeline"])


def job_to_response(job: VideoPipelineJob, items: list[VideoPipelineJobItem]) -> dict[str, object]:
    data = VideoPipelineJobRead.model_validate(job).model_copy(
        update={"items": [VideoPipelineJobItemRead.model_validate(item) for item in items]}
    )
    return data.model_dump(mode="json")


@router.post("/jobs")
def post_create_pipeline_job(
    project_id: UUID,
    payload: VideoPipelineJobCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    job = create_pipeline_job(db, current_user, project_id, payload)
    return {"success": True, "data": job_to_response(job, [])}


@router.get("/jobs")
def get_pipeline_jobs(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    jobs = list_pipeline_jobs_for_project(db, current_user, project_id)
    return {"success": True, "data": [job_to_response(job, []) for job in jobs]}


@router.get("/jobs/{job_id}")
def get_pipeline_job(
    project_id: UUID,
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    job, items = get_pipeline_job_detail(db, current_user, project_id, job_id)
    return {"success": True, "data": job_to_response(job, items)}


@router.post("/jobs/{job_id}/run")
def post_run_pipeline_job(
    project_id: UUID,
    job_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    job = start_pipeline_job(db, current_user, project_id, job_id)
    background_tasks.add_task(run_video_pipeline_job, job.id, current_user.id, project_id)
    return {"success": True, "data": job_to_response(job, [])}


@router.post("/jobs/{job_id}/retry-failed")
def post_retry_failed_pipeline_job(
    project_id: UUID,
    job_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    job = prepare_retry_failed(db, current_user, project_id, job_id)
    background_tasks.add_task(run_video_pipeline_job, job.id, current_user.id, project_id)
    return {"success": True, "data": job_to_response(job, [])}


@router.post("/jobs/{job_id}/cancel")
def post_cancel_pipeline_job(
    project_id: UUID,
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    job = cancel_pipeline_job(db, current_user, project_id, job_id)
    return {"success": True, "data": job_to_response(job, [])}
