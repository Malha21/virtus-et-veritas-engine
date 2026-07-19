from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.lesson_generation import (
    GenerateAllLessonsRequest,
    LessonGenerationApprovalRequest,
    LessonGenerationDetail,
    LessonGenerationListResponse,
    LessonGenerationRejectionRequest,
    LessonGenerationRepairRequest,
    LessonGenerationRequest,
    LessonGenerationResponse,
    LessonGenerationUpdate,
    LessonGenerationValidationResponse,
    LessonRegenerationRequest,
)
from app.schemas.processing import ProcessingJobResponse
from app.services.coverage_plan_service import get_lesson_for_user
from app.services.lesson_generation_service import (
    approve_generation,
    build_generation_detail,
    edit_generation_manual,
    get_generation_by_version,
    get_latest_course_lesson_generation_job,
    get_latest_generation,
    get_latest_lesson_generation_job,
    load_plan_and_module,
    list_generations,
    get_approved_generation,
    reject_generation,
    run_course_lesson_generation,
    run_lesson_generation,
    start_course_lesson_generation,
    start_lesson_generation,
    start_lesson_regeneration,
    start_repair_missing_items,
    cancel_course_lesson_generation,
    retry_failed_course_lessons,
    validate_generation,
)
from app.services.project_service import get_project_by_id

lesson_router = APIRouter(prefix="/coverage-plan/lessons", tags=["lesson-generation"])
course_router = APIRouter(prefix="/projects/{project_id}/lessons", tags=["lesson-generation"])


def _require_generation(db: Session, current_user: User, lesson_id: UUID, version: int):
    lesson = get_lesson_for_user(db, current_user, lesson_id)
    plan, module = load_plan_and_module(db, lesson)
    generation = get_generation_by_version(db, lesson.id, version)
    return lesson, plan, module, generation


@lesson_router.post("/{lesson_id}/generate")
def generate_lesson_endpoint(
    lesson_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: LessonGenerationRequest | None = None,
) -> dict[str, object]:
    force = payload.force if payload else False
    job = start_lesson_generation(db, current_user, lesson_id, force=force)
    if job.status == "pending":
        background_tasks.add_task(run_lesson_generation, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@lesson_router.post("/{lesson_id}/regenerate")
def regenerate_lesson_endpoint(
    lesson_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: LessonRegenerationRequest,
) -> dict[str, object]:
    job = start_lesson_regeneration(db, current_user, lesson_id, mode=payload.mode, feedback=payload.feedback)
    if job.status == "pending":
        background_tasks.add_task(run_lesson_generation, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@lesson_router.get("/{lesson_id}/generations")
def list_lesson_generations_endpoint(
    lesson_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    lesson = get_lesson_for_user(db, current_user, lesson_id)
    generations = list_generations(db, lesson.id)
    approved = get_approved_generation(db, lesson.id)
    data = LessonGenerationListResponse(
        items=[LessonGenerationResponse.model_validate(g) for g in generations],
        latest_version=generations[0].version if generations else None,
        approved_version=approved.version if approved else None,
    )
    return {"success": True, "data": data.model_dump(mode="json")}


@lesson_router.get("/{lesson_id}/generations/latest")
def get_latest_lesson_generation_endpoint(
    lesson_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    lesson = get_lesson_for_user(db, current_user, lesson_id)
    _plan, module = load_plan_and_module(db, lesson)
    generation = get_latest_generation(db, lesson.id)
    if generation is None:
        return {"success": True, "data": None}
    data = build_generation_detail(db, generation, lesson, module)
    return {"success": True, "data": data.model_dump(mode="json")}


@lesson_router.get("/{lesson_id}/generations/{version}")
def get_lesson_generation_version_endpoint(
    lesson_id: UUID,
    version: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    lesson, _plan, module, generation = _require_generation(db, current_user, lesson_id, version)
    data = build_generation_detail(db, generation, lesson, module)
    return {"success": True, "data": data.model_dump(mode="json")}


@lesson_router.patch("/{lesson_id}/generations/{version}")
def edit_lesson_generation_endpoint(
    lesson_id: UUID,
    version: int,
    payload: LessonGenerationUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    lesson, plan, _module, generation = _require_generation(db, current_user, lesson_id, version)
    latest = get_latest_generation(db, lesson.id)
    if latest is None or latest.id != generation.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só é possível editar a versão mais recente; outra versão já foi criada nesse meio tempo.",
        )
    updated = edit_generation_manual(
        db, current_user, lesson, plan, payload.generated_content, payload.structured_content
    )
    data = LessonGenerationResponse.model_validate(updated)
    return {"success": True, "data": data.model_dump(mode="json")}


@lesson_router.post("/{lesson_id}/generations/{version}/validate")
def validate_lesson_generation_endpoint(
    lesson_id: UUID,
    version: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    lesson, plan, _module, generation = _require_generation(db, current_user, lesson_id, version)
    result: LessonGenerationValidationResponse = validate_generation(db, lesson, plan, generation)
    return {"success": True, "data": result.model_dump(mode="json")}


@lesson_router.post("/{lesson_id}/generations/{version}/repair")
def repair_lesson_generation_endpoint(
    lesson_id: UUID,
    version: int,
    payload: LessonGenerationRepairRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    lesson, plan, _module, generation = _require_generation(db, current_user, lesson_id, version)
    job = start_repair_missing_items(
        db,
        current_user,
        lesson,
        plan,
        generation,
        missing_source_item_ids=payload.missing_source_item_ids,
        validation_notes=payload.validation_notes,
    )
    if job.status == "pending":
        background_tasks.add_task(run_lesson_generation, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@lesson_router.post("/{lesson_id}/generations/{version}/approve")
def approve_lesson_generation_endpoint(
    lesson_id: UUID,
    version: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: LessonGenerationApprovalRequest | None = None,
) -> dict[str, object]:
    lesson, plan, _module, generation = _require_generation(db, current_user, lesson_id, version)
    approved = approve_generation(db, current_user, lesson, plan, generation)
    data = LessonGenerationResponse.model_validate(approved)
    return {"success": True, "data": data.model_dump(mode="json")}


@lesson_router.post("/{lesson_id}/generations/{version}/reject")
def reject_lesson_generation_endpoint(
    lesson_id: UUID,
    version: int,
    payload: LessonGenerationRejectionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _lesson, _plan, _module, generation = _require_generation(db, current_user, lesson_id, version)
    rejected = reject_generation(db, current_user, generation, payload.reason)
    data = LessonGenerationResponse.model_validate(rejected)
    return {"success": True, "data": data.model_dump(mode="json")}


@lesson_router.get("/{lesson_id}/generation-job")
def get_lesson_generation_job_endpoint(
    lesson_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    lesson = get_lesson_for_user(db, current_user, lesson_id)
    job = get_latest_lesson_generation_job(db, lesson.id)
    if job is None:
        return {"success": True, "data": None}
    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


# --------------------------------------------------------------------------
# Geracao em lote (uma chamada de IA por aula; orquestrada por projeto)
# --------------------------------------------------------------------------

@course_router.post("/generate-all")
def generate_all_lessons_endpoint(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: GenerateAllLessonsRequest | None = None,
) -> dict[str, object]:
    force = payload.force if payload else False
    only_pending = payload.only_pending if payload else True
    job = start_course_lesson_generation(db, current_user, project_id, force=force, only_pending=only_pending)
    if job.status == "pending":
        background_tasks.add_task(run_course_lesson_generation, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@course_router.get("/generation-job")
def get_course_lesson_generation_job_endpoint(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    job = get_latest_course_lesson_generation_job(db, project.id)
    if job is None:
        return {"success": True, "data": None}
    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@course_router.post("/retry-failed")
def retry_failed_lessons_endpoint(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    job = retry_failed_course_lessons(db, current_user, project_id)
    if job.status == "pending":
        background_tasks.add_task(run_course_lesson_generation, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@course_router.post("/cancel-generation")
def cancel_lesson_generation_endpoint(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    job = cancel_course_lesson_generation(db, current_user, project_id)
    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}
