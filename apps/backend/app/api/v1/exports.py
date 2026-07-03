from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.export_service import (
    export_complementary_materials_pdf,
    export_full_course_pdf,
    export_lesson_scripts_pdf,
    export_presentation_pdf,
    export_quizzes_pdf,
)

router = APIRouter(prefix="/projects/{project_id}/exports", tags=["exports"])


def safe_filename(value: object) -> str:
    text = str(value or "presentation").strip().lower()
    cleaned = []
    for char in text:
        if char.isalnum():
            cleaned.append(char)
        elif char in {"-", "_", " "}:
            cleaned.append("-")
    filename = "".join(cleaned).strip("-")
    while "--" in filename:
        filename = filename.replace("--", "-")
    return filename or "presentation"


@router.get("/presentation.pdf")
def get_presentation_pdf(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    project, pdf_bytes = export_presentation_pdf(db, current_user, project_id)
    filename = f"presentation-{safe_filename(project.slug or project.id)}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.get("/lesson-scripts.pdf")
def get_lesson_scripts_pdf(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    project, pdf_bytes = export_lesson_scripts_pdf(db, current_user, project_id)
    filename = f"lesson-scripts-{safe_filename(project.slug or project.id)}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.get("/quizzes.pdf")
def get_quizzes_pdf(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    project, pdf_bytes = export_quizzes_pdf(db, current_user, project_id)
    filename = f"quizzes-{safe_filename(project.slug or project.id)}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.get("/complementary-materials.pdf")
def get_complementary_materials_pdf(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    project, pdf_bytes = export_complementary_materials_pdf(db, current_user, project_id)
    filename = f"complementary-materials-{safe_filename(project.slug or project.id)}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.get("/full-course.pdf")
def get_full_course_pdf(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    project, pdf_bytes = export_full_course_pdf(db, current_user, project_id)
    filename = f"full-course-{safe_filename(project.slug or project.id)}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)
