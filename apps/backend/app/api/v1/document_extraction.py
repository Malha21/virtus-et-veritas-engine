from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.document_block import DocumentBlockListResponse, DocumentBlockResponse
from app.schemas.document_extraction import DocumentExtractionRequest, DocumentReprocessRequest
from app.schemas.document_page import (
    DocumentPageDetailResponse,
    DocumentPageListResponse,
    DocumentPageResponse,
)
from app.schemas.processing import ProcessingJobResponse
from app.services.document_extraction_service import (
    create_extraction_job,
    create_reprocess_job,
    get_block_counts_by_page,
    get_document_page_detail,
    get_latest_extraction_job,
    get_project_file_for_extraction,
    build_extraction_summary,
    list_document_blocks,
    list_document_pages,
    run_document_extraction,
)

router = APIRouter(prefix="/projects/{project_id}/files/{file_id}", tags=["document-extraction"])


def _page_to_response(page, block_count: int) -> DocumentPageResponse:
    data = DocumentPageResponse.model_validate(page)
    data.block_count = block_count
    return data


@router.post("/extraction")
def start_extraction(
    project_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: DocumentExtractionRequest | None = None,
) -> dict[str, object]:
    project, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    force = payload.force if payload else False
    job = create_extraction_job(db, current_user, project, project_file, scope="all", force=force)

    if job.status == "pending":
        background_tasks.add_task(run_document_extraction, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/extraction")
def get_extraction_summary(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    summary = build_extraction_summary(db, project_file)
    return {"success": True, "data": summary.model_dump(mode="json")}


@router.get("/extraction/job")
def get_extraction_job(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    job = get_latest_extraction_job(db, project_file.id)
    if job is None:
        return {"success": True, "data": None}
    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/extraction/reprocess")
def reprocess_extraction(
    project_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: DocumentReprocessRequest | None = None,
) -> dict[str, object]:
    scope = payload.scope if payload else "failed"
    page_number = payload.page_number if payload else None
    job = create_reprocess_job(db, current_user, project_id, file_id, scope, page_number)

    if job.status == "pending":
        background_tasks.add_task(run_document_extraction, job.id, current_user.id)

    data = ProcessingJobResponse.model_validate(job)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/pages")
def get_pages(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    extraction_status: str | None = None,
    requires_ocr: bool | None = None,
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    pages, total = list_document_pages(
        db,
        project_file,
        page=page,
        page_size=page_size,
        extraction_status=extraction_status,
        requires_ocr=requires_ocr,
    )
    counts = get_block_counts_by_page(db, [p.id for p in pages])
    items = [_page_to_response(p, counts.get(p.id, 0)) for p in pages]
    total_pages = (total + page_size - 1) // page_size if total else 0

    response = DocumentPageListResponse(items=items, page=page, page_size=page_size, total=total, total_pages=total_pages)
    return {"success": True, "data": response.model_dump(mode="json")}


@router.get("/pages/{page_number}")
def get_page_detail(
    project_id: UUID,
    file_id: UUID,
    page_number: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    doc_page, blocks = get_document_page_detail(db, project_file, page_number)

    block_responses = [DocumentBlockResponse.model_validate(block) for block in blocks]
    page_response = _page_to_response(doc_page, len(block_responses))
    detail = DocumentPageDetailResponse(**page_response.model_dump(), blocks=block_responses)
    return {"success": True, "data": detail.model_dump(mode="json")}


@router.get("/blocks")
def get_blocks(
    project_id: UUID,
    file_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page_number: int | None = None,
    block_type: str | None = None,
) -> dict[str, object]:
    _, project_file = get_project_file_for_extraction(db, current_user, project_id, file_id)
    blocks = list_document_blocks(db, project_file, page_number=page_number, block_type=block_type)
    items = [DocumentBlockResponse.model_validate(block) for block in blocks]
    response = DocumentBlockListResponse(items=items)
    return {"success": True, "data": response.model_dump(mode="json")}
