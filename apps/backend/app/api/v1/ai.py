from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.ai import GenerateStructureResponse
from app.services.ai_orchestrator_service import generate_project_structure

router = APIRouter(prefix="/projects/{project_id}", tags=["ai"])


@router.post("/generate-structure")
def generate_structure(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    result = generate_project_structure(db, current_user, project_id)
    data = GenerateStructureResponse(**result)
    return {"success": True, "data": data.model_dump(mode="json")}
