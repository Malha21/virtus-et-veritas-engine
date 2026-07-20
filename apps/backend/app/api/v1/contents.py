from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.generated_content import GeneratedContent
from app.models.user import User
from app.schemas.content import GeneratedContentListResponse, GeneratedContentResponse, GeneratedContentUpdate
from app.services.project_service import get_project_by_id

router = APIRouter(prefix="/projects/{project_id}/contents", tags=["contents"])

ALLOWED_CONTENT_STATUSES = {"draft", "generated", "reviewed", "approved", "rejected", "archived"}


def get_content_or_404(
    db: Session,
    current_user: User,
    project_id: UUID,
    content_id: UUID,
) -> GeneratedContent:
    get_project_by_id(db, current_user, project_id)
    content = db.execute(
        select(GeneratedContent).where(
            GeneratedContent.id == content_id,
            GeneratedContent.project_id == project_id,
            GeneratedContent.organization_id == current_user.organization_id,
        )
    ).scalar_one_or_none()

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conteudo nao encontrado.",
        )

    return content


@router.get("")
def list_project_contents(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    content_type: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> dict[str, object]:
    get_project_by_id(db, current_user, project_id)
    filters = [
        GeneratedContent.project_id == project_id,
        GeneratedContent.organization_id == current_user.organization_id,
    ]
    if content_type:
        filters.append(GeneratedContent.content_type == content_type)
    if status_filter:
        filters.append(GeneratedContent.status == status_filter)

    statement = select(GeneratedContent).where(*filters).order_by(GeneratedContent.created_at.desc())
    contents = list(db.execute(statement).scalars().all())
    data = GeneratedContentListResponse(
        items=[GeneratedContentResponse.model_validate(content) for content in contents]
    )
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/{content_id}")
def get_project_content(
    project_id: UUID,
    content_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    content = get_content_or_404(db, current_user, project_id, content_id)
    data = GeneratedContentResponse.model_validate(content)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.patch("/{content_id}")
def update_project_content(
    project_id: UUID,
    content_id: UUID,
    payload: GeneratedContentUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    content = get_content_or_404(db, current_user, project_id, content_id)
    updates = payload.model_dump(exclude_unset=True)

    if "status" in updates and updates["status"] not in ALLOWED_CONTENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Status de conteudo invalido.",
        )

    for field, value in updates.items():
        setattr(content, field, value)

    db.add(content)
    db.commit()
    db.refresh(content)
    data = GeneratedContentResponse.model_validate(content)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/{content_id}/approve")
def approve_project_content(
    project_id: UUID,
    content_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    content = get_content_or_404(db, current_user, project_id, content_id)
    content.status = "approved"
    db.add(content)
    db.commit()
    db.refresh(content)
    data = GeneratedContentResponse.model_validate(content)
    return {"success": True, "data": data.model_dump(mode="json")}
