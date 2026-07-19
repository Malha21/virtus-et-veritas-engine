from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.document_block import DocumentBlock
from app.models.document_page import DocumentPage
from app.models.user import User
from app.schemas.processing import ProcessingJobResponse
from app.schemas.source_content_item import SourceContentItemListResponse, SourceContentItemResponse
from app.schemas.source_inventory import (
    InventoryValidationResult,
    SourceContentItemBlockResponse,
    SourceContentItemDetailResponse,
    SourceInventoryGenerateRequest,
    SourceInventoryItemManualUpdate,
    SourceInventoryReprocessRequest,
    SourceInventorySummary,
    SourceItemDependencyResponse,
)
from app.services.document_extraction_service import get_project_file_for_extraction
from app.services.source_inventory_service import (
    build_inventory_summary,
    get_inventory_item_detail,
    get_latest_inventory_job,
    list_inventory_items,
    run_source_inventory,
    set_inventory_item_status,
    start_inventory_generation,
    start_inventory_reprocess,
    update_inventory_item,
)
from app.services.source_inventory_validator import validate_persisted_inventory

router = APIRouter(prefix="/projects/{project_id}/files/{file_id}/inventory", tags=["source-inventory"])


@router.post("/generate")
def generate_inventory_endpoint(
    project_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: SourceInventoryGenerateRequest | None = None,
) -> dict[str, object]:
    force = payload.force if payload else False
    continue_with_alerts = payload.continue_with_alerts if payload else False
    job = start_inventory_generation(
        db, current_user, project_id, file_id, force=force, continue_with_alerts=continue_with_alerts
    )
    if job.status == "pending":
        background_tasks.add_task(run_source_inventory, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/reprocess")
def reprocess_inventory_endpoint(
    project_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: SourceInventoryReprocessRequest,
) -> dict[str, object]:
    job = start_inventory_reprocess(
        db,
        current_user,
        project_id,
        file_id,
        mode=payload.mode,
        page_numbers=payload.page_numbers,
        continue_with_alerts=payload.continue_with_alerts,
    )
    if job.status == "pending":
        background_tasks.add_task(run_source_inventory, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/summary")
def get_inventory_summary_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    summary = build_inventory_summary(db, project, project_file)
    return {"success": True, "data": summary.model_dump(mode="json")}


@router.get("/job")
def get_inventory_job_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    job = get_latest_inventory_job(db, project_file.id)
    if job is None:
        return {"success": True, "data": None}
    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/validate")
def validate_inventory_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    items, _total = list_inventory_items(db, project_file, page=1, page_size=100000)
    result: InventoryValidationResult = validate_persisted_inventory(items)
    return {"success": True, "data": result.model_dump(mode="json")}


@router.get("")
def list_inventory_endpoint(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    content_type: str | None = None,
    importance: str | None = None,
    status: str | None = None,
    page_number: int | None = None,
    requires_review: bool | None = None,
    possible_duplicate: bool | None = None,
    search: str | None = None,
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    items, total = list_inventory_items(
        db,
        project_file,
        page=page,
        page_size=page_size,
        content_type=content_type,
        importance=importance,
        status_filter=status,
        page_number=page_number,
        requires_review=requires_review,
        possible_duplicate=possible_duplicate,
        search=search,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    response = SourceContentItemListResponse(
        items=[SourceContentItemResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )
    return {"success": True, "data": response.model_dump(mode="json")}


def _block_to_response(assoc, block: DocumentBlock, page_number: int) -> SourceContentItemBlockResponse:
    return SourceContentItemBlockResponse(
        id=assoc.id,
        source_item_id=assoc.source_item_id,
        block_id=assoc.block_id,
        block_code=block.block_code,
        page_number=page_number,
        source_order=assoc.source_order,
        is_primary=assoc.is_primary,
        created_at=assoc.created_at,
    )


@router.get("/{source_item_id}")
def get_inventory_item_endpoint(
    project_id: UUID,
    file_id: UUID,
    source_item_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    item, blocks, dependencies, dependents = get_inventory_item_detail(db, project_file, source_item_id)

    block_responses = []
    for assoc in blocks:
        block = db.get(DocumentBlock, assoc.block_id)
        if block is None:
            continue
        page = db.get(DocumentPage, block.page_id)
        if page is None:
            continue
        block_responses.append(_block_to_response(assoc, block, page.page_number))

    detail = SourceContentItemDetailResponse(
        **SourceContentItemResponse.model_validate(item).model_dump(),
        blocks=block_responses,
        dependencies=[SourceItemDependencyResponse.model_validate(d) for d in dependencies],
        dependents=[SourceItemDependencyResponse.model_validate(d) for d in dependents],
    )
    return {"success": True, "data": detail.model_dump(mode="json")}


@router.patch("/{source_item_id}")
def update_inventory_item_endpoint(
    project_id: UUID,
    file_id: UUID,
    source_item_id: UUID,
    payload: SourceInventoryItemManualUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    item = update_inventory_item(
        db,
        project_file,
        source_item_id,
        title=payload.title,
        normalized_content=payload.normalized_content,
        content_type=payload.content_type,
        importance=payload.importance,
        review_note=payload.review_note,
    )
    data = SourceContentItemResponse.model_validate(item)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/{source_item_id}/approve")
def approve_inventory_item_endpoint(
    project_id: UUID,
    file_id: UUID,
    source_item_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    item = set_inventory_item_status(db, project_file, source_item_id, "approved")
    data = SourceContentItemResponse.model_validate(item)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/{source_item_id}/reject")
def reject_inventory_item_endpoint(
    project_id: UUID,
    file_id: UUID,
    source_item_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    item = set_inventory_item_status(db, project_file, source_item_id, "rejected")
    data = SourceContentItemResponse.model_validate(item)
    return {"success": True, "data": data.model_dump(mode="json")}
