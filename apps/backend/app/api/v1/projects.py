from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectListItem,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import (
    archive_project,
    create_project,
    get_project_by_id,
    list_projects,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def get_projects(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    product_type: str | None = None,
    processing_status: str | None = None,
    search: str | None = None,
) -> dict[str, object]:
    projects, total = list_projects(
        db=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
        status_filter=status,
        product_type=product_type,
        processing_status=processing_status,
        search=search,
    )
    data = ProjectListResponse(
        items=[ProjectListItem.model_validate(project) for project in projects],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("")
def post_project(
    payload: ProjectCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project = create_project(db, current_user, payload)
    data = ProjectResponse.model_validate(project)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/{project_id}")
def get_project(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    data = ProjectResponse.model_validate(project)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.patch("/{project_id}")
def patch_project(
    project_id: UUID,
    payload: ProjectUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project = update_project(db, current_user.organization_id, project_id, payload)
    data = ProjectResponse.model_validate(project)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.delete("/{project_id}")
def delete_project(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    archive_project(db, current_user.organization_id, project_id)
    return {"success": True, "data": {"message": "Projeto arquivado com sucesso."}}
