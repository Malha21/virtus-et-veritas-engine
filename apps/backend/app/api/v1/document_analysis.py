from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.content import GeneratedContentResponse
from app.services.document_analysis_service import (
    generate_document_analysis,
    get_latest_document_analysis,
)

router = APIRouter(prefix="/projects/{project_id}/document-analysis", tags=["document-analysis"])


@router.get("")
def get_project_document_analysis(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    content = get_latest_document_analysis(db, current_user, project_id)
    data = GeneratedContentResponse.model_validate(content).model_dump(mode="json") if content else None
    return {"success": True, "data": data}


@router.post("/generate")
def generate_project_document_analysis(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    content = generate_document_analysis(db, current_user, project_id)
    data = GeneratedContentResponse.model_validate(content)
    return {"success": True, "data": data.model_dump(mode="json")}
