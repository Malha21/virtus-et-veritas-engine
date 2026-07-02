from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.content import GeneratedContentResponse
from app.schemas.educational_content import EducationalContentSummaryResponse, GenerateEducationalContentResponse
from app.services.educational_content_service import generate_educational_content, list_educational_content

router = APIRouter(prefix="/projects/{project_id}", tags=["educational-content"])


@router.post("/generate-educational-content")
def generate_project_educational_content(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    result = generate_educational_content(db, current_user, project_id)
    data = GenerateEducationalContentResponse(**result)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/educational-content")
def get_project_educational_content(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    grouped = list_educational_content(db, current_user, project_id)
    data = EducationalContentSummaryResponse(
        lesson_scripts=[GeneratedContentResponse.model_validate(item) for item in grouped["lesson_scripts"]],
        module_quizzes=[GeneratedContentResponse.model_validate(item) for item in grouped["module_quizzes"]],
        complementary_materials=[
            GeneratedContentResponse.model_validate(item) for item in grouped["complementary_materials"]
        ],
        course_summaries=[GeneratedContentResponse.model_validate(item) for item in grouped["course_summaries"]],
    )
    return {"success": True, "data": data.model_dump(mode="json")}
