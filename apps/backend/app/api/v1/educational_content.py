from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.content import GeneratedContentResponse
from app.schemas.educational_content import (
    ComplementaryMaterialUpdateRequest,
    EducationalContentSummaryResponse,
    GenerateEducationalContentRequest,
    GenerateEducationalContentResponse,
    LessonScriptUpdateRequest,
    ModuleQuizUpdateRequest,
    PresentationDeckUpdateRequest,
)
from app.services.educational_content_service import (
    generate_educational_content,
    list_educational_content,
    update_complementary_material,
    update_lesson_script,
    update_module_quiz,
    update_presentation_deck,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["educational-content"])


@router.post("/generate-educational-content")
def generate_project_educational_content(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: GenerateEducationalContentRequest | None = None,
) -> dict[str, object]:
    generation_language = payload.generation_language if payload else "pt-BR"
    result = generate_educational_content(db, current_user, project_id, generation_language)
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
        presentation_decks=[GeneratedContentResponse.model_validate(item) for item in grouped["presentation_decks"]],
    )
    return {"success": True, "data": data.model_dump(mode="json")}


@router.put("/educational-content/presentation-deck")
def put_project_presentation_deck(
    project_id: UUID,
    payload: PresentationDeckUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    content = update_presentation_deck(
        db,
        current_user,
        project_id,
        payload.model_dump(mode="json"),
    )
    data = GeneratedContentResponse.model_validate(content)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.put("/educational-content/lesson-scripts/{content_id}")
def put_project_lesson_script(
    project_id: UUID,
    content_id: UUID,
    payload: LessonScriptUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    content = update_lesson_script(
        db,
        current_user,
        project_id,
        content_id,
        payload.model_dump(mode="json"),
    )
    data = GeneratedContentResponse.model_validate(content)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.put("/educational-content/module-quizzes/{content_id}")
def put_project_module_quiz(
    project_id: UUID,
    content_id: UUID,
    payload: ModuleQuizUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    content = update_module_quiz(
        db,
        current_user,
        project_id,
        content_id,
        payload.model_dump(mode="json"),
    )
    data = GeneratedContentResponse.model_validate(content)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.put("/educational-content/complementary-materials/{content_id}")
def put_project_complementary_material(
    project_id: UUID,
    content_id: UUID,
    payload: ComplementaryMaterialUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    content = update_complementary_material(
        db,
        current_user,
        project_id,
        content_id,
        payload.model_dump(mode="json"),
    )
    data = GeneratedContentResponse.model_validate(content)
    return {"success": True, "data": data.model_dump(mode="json")}
