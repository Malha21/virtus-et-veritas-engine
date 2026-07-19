from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.coverage_plan_lesson import CoveragePlanLesson
from app.models.user import User
from app.schemas.coverage_plan import (
    CoveragePlanApprovalRequest,
    CoveragePlanGenerateRequest,
    CoveragePlanLessonMergeRequest,
    CoveragePlanLessonResponse,
    CoveragePlanLessonSourceItemAddRequest,
    CoveragePlanLessonSplitRequest,
    CoveragePlanLessonUpdate,
    CoveragePlanModuleResponse,
    CoveragePlanModuleUpdate,
    CoveragePlanRegenerateRequest,
    CoveragePlanResponse,
    CoveragePlanValidationResponse,
    CoveragePlanVersionResponse,
    UnmappedSourceItemResponse,
)
from app.schemas.processing import ProcessingJobResponse
from app.services.coverage_plan_service import (
    add_source_item_to_lesson,
    approve_plan,
    build_coverage_plan_summary,
    build_plan_response_data,
    get_latest_coverage_plan_job,
    get_latest_plan,
    get_lesson_for_user,
    get_module_for_user,
    get_plan_by_version,
    list_plan_versions,
    list_unmapped_items,
    merge_lessons_manual,
    recalculate_lesson_estimates,
    remove_source_item_from_lesson,
    run_coverage_plan_generation,
    split_lesson_manual,
    start_coverage_plan_generation,
    start_coverage_plan_regenerate,
    update_lesson,
    update_module,
)
from app.services.coverage_plan_validator import validate_persisted_coverage
from app.services.document_extraction_service import get_project_file_for_extraction

router = APIRouter(prefix="/projects/{project_id}/files/{file_id}/coverage-plan", tags=["coverage-plan"])
lessons_router = APIRouter(prefix="/coverage-plan", tags=["coverage-plan"])


def _require_plan(db: Session, project_id: UUID):
    plan = get_latest_plan(db, project_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhum plano de cobertura gerado ainda.")
    return plan


@router.post("/generate")
def generate_coverage_plan_endpoint(
    project_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: CoveragePlanGenerateRequest | None = None,
) -> dict[str, object]:
    force = payload.force if payload else False
    continue_with_alerts = payload.continue_with_alerts if payload else False
    job = start_coverage_plan_generation(
        db, current_user, project_id, file_id, force=force, continue_with_alerts=continue_with_alerts
    )
    if job.status == "pending":
        background_tasks.add_task(run_coverage_plan_generation, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/regenerate")
def regenerate_coverage_plan_endpoint(
    project_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: CoveragePlanRegenerateRequest,
) -> dict[str, object]:
    job = start_coverage_plan_regenerate(db, current_user, project_id, file_id, mode=payload.mode)
    if job.status == "pending":
        background_tasks.add_task(run_coverage_plan_generation, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/summary")
def get_coverage_plan_summary_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    summary = build_coverage_plan_summary(db, project, project_file)
    return {"success": True, "data": summary.model_dump(mode="json")}


@router.get("/job")
def get_coverage_plan_job_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    job = get_latest_coverage_plan_job(db, project_file.id)
    if job is None:
        return {"success": True, "data": None}
    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("")
def get_coverage_plan_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    get_project_file_for_extraction(db, current_user, project_id, file_id)
    plan = _require_plan(db, project_id)
    data = CoveragePlanResponse.model_validate(build_plan_response_data(db, plan))
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/versions")
def list_coverage_plan_versions_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    get_project_file_for_extraction(db, current_user, project_id, file_id)
    versions = list_plan_versions(db, project_id)
    data = [CoveragePlanVersionResponse.model_validate(v) for v in versions]
    return {"success": True, "data": [d.model_dump(mode="json") for d in data]}


@router.get("/versions/{version}")
def get_coverage_plan_version_endpoint(
    project_id: UUID,
    file_id: UUID,
    version: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    get_project_file_for_extraction(db, current_user, project_id, file_id)
    plan = get_plan_by_version(db, project_id, version)
    data = CoveragePlanResponse.model_validate(build_plan_response_data(db, plan))
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/validate")
def validate_coverage_plan_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    get_project_file_for_extraction(db, current_user, project_id, file_id)
    plan = _require_plan(db, project_id)
    result: CoveragePlanValidationResponse = validate_persisted_coverage(db, plan)
    return {"success": True, "data": result.model_dump(mode="json")}


@router.post("/recalculate")
def recalculate_coverage_plan_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    get_project_file_for_extraction(db, current_user, project_id, file_id)
    plan = _require_plan(db, project_id)
    lesson_ids = db.execute(
        select(CoveragePlanLesson.id).where(CoveragePlanLesson.coverage_plan_id == plan.id)
    ).scalars().all()
    for lesson_id in lesson_ids:
        recalculate_lesson_estimates(db, lesson_id)

    result = validate_persisted_coverage(db, plan)
    return {"success": True, "data": result.model_dump(mode="json")}


@router.get("/unmapped-items")
def list_unmapped_items_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    get_project_file_for_extraction(db, current_user, project_id, file_id)
    plan = _require_plan(db, project_id)
    items = list_unmapped_items(db, plan)
    return {"success": True, "data": [UnmappedSourceItemResponse.model_validate(i).model_dump(mode="json") for i in items]}


@router.post("/approve")
def approve_coverage_plan_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: CoveragePlanApprovalRequest | None = None,
) -> dict[str, object]:
    get_project_file_for_extraction(db, current_user, project_id, file_id)
    plan = _require_plan(db, project_id)
    approved = approve_plan(db, current_user, plan)
    data = CoveragePlanResponse.model_validate(build_plan_response_data(db, approved))
    return {"success": True, "data": data.model_dump(mode="json")}


# --------------------------------------------------------------------------
# Rotas por module_id/lesson_id (nao aninhadas em project/file)
# --------------------------------------------------------------------------

@lessons_router.patch("/modules/{module_id}")
def update_module_endpoint(
    module_id: UUID,
    payload: CoveragePlanModuleUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    module = get_module_for_user(db, current_user, module_id)
    updated = update_module(
        db,
        module,
        title=payload.title,
        description=payload.description,
        learning_objective=payload.learning_objective,
        module_order=payload.module_order,
        status=payload.status,
    )
    data = CoveragePlanModuleResponse.model_validate(updated)
    return {"success": True, "data": data.model_dump(mode="json")}


@lessons_router.patch("/lessons/{lesson_id}")
def update_lesson_endpoint(
    lesson_id: UUID,
    payload: CoveragePlanLessonUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    lesson = get_lesson_for_user(db, current_user, lesson_id)
    updated = update_lesson(
        db,
        lesson,
        current_user=current_user,
        title=payload.title,
        description=payload.description,
        learning_objective=payload.learning_objective,
        lesson_order=payload.lesson_order,
        module_id=payload.module_id,
        status=payload.status,
    )
    data = CoveragePlanLessonResponse.model_validate(updated)
    return {"success": True, "data": data.model_dump(mode="json")}


@lessons_router.post("/lessons/{lesson_id}/recalculate")
def recalculate_lesson_endpoint(
    lesson_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    get_lesson_for_user(db, current_user, lesson_id)
    lesson = recalculate_lesson_estimates(db, lesson_id)
    data = CoveragePlanLessonResponse.model_validate(lesson)
    return {"success": True, "data": data.model_dump(mode="json")}


@lessons_router.post("/lessons/{lesson_id}/split")
def split_lesson_endpoint(
    lesson_id: UUID,
    payload: CoveragePlanLessonSplitRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    get_lesson_for_user(db, current_user, lesson_id)
    first, second = split_lesson_manual(
        db,
        lesson_id,
        first_title=payload.first_title,
        second_title=payload.second_title,
        first_source_item_ids=payload.first_source_item_ids,
        second_source_item_ids=payload.second_source_item_ids,
        first_description=payload.first_description,
        second_description=payload.second_description,
        first_learning_objective=payload.first_learning_objective,
        second_learning_objective=payload.second_learning_objective,
    )
    return {
        "success": True,
        "data": {
            "first": CoveragePlanLessonResponse.model_validate(first).model_dump(mode="json"),
            "second": CoveragePlanLessonResponse.model_validate(second).model_dump(mode="json"),
        },
    }


@lessons_router.post("/lessons/merge")
def merge_lessons_endpoint(
    payload: CoveragePlanLessonMergeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    for lesson_id in payload.lesson_ids:
        get_lesson_for_user(db, current_user, lesson_id)
    merged = merge_lessons_manual(
        db,
        payload.lesson_ids,
        title=payload.title,
        description=payload.description,
        learning_objective=payload.learning_objective,
    )
    data = CoveragePlanLessonResponse.model_validate(merged)
    return {"success": True, "data": data.model_dump(mode="json")}


@lessons_router.post("/lessons/{lesson_id}/source-items")
def add_lesson_source_item_endpoint(
    lesson_id: UUID,
    payload: CoveragePlanLessonSourceItemAddRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    get_lesson_for_user(db, current_user, lesson_id)
    lesson = add_source_item_to_lesson(
        db,
        lesson_id,
        payload.source_item_id,
        current_user=current_user,
        coverage_type=payload.coverage_type,
        is_required=payload.is_required,
        source_order_in_lesson=payload.source_order_in_lesson,
        coverage_notes=payload.coverage_notes,
    )
    data = CoveragePlanLessonResponse.model_validate(lesson)
    return {"success": True, "data": data.model_dump(mode="json")}


@lessons_router.delete("/lessons/{lesson_id}/source-items/{source_item_id}")
def remove_lesson_source_item_endpoint(
    lesson_id: UUID,
    source_item_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    get_lesson_for_user(db, current_user, lesson_id)
    lesson = remove_source_item_from_lesson(db, lesson_id, source_item_id)
    data = CoveragePlanLessonResponse.model_validate(lesson)
    return {"success": True, "data": data.model_dump(mode="json")}
