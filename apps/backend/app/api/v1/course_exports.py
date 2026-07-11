from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.course_export import CourseExport
from app.models.user import User
from app.schemas.course_export import CourseExportCreate, CourseExportRead
from app.services.course_export_service import (
    create_course_export,
    delete_course_export,
    get_course_export,
    get_course_export_download_path,
    list_course_exports,
    run_course_export_job,
)

router = APIRouter(prefix="/projects/{project_id}/exports", tags=["course-exports"])


def export_to_response(export: CourseExport) -> dict[str, object]:
    has_download = export.status == "completed" and bool(export.file_path)
    data = CourseExportRead.model_validate(export).model_copy(
        update={
            "download_url": (
                f"/api/v1/projects/{export.project_id}/exports/{export.id}/download" if has_download else None
            )
        }
    )
    return data.model_dump(mode="json")


@router.post("/course")
def post_create_course_export(
    project_id: UUID,
    payload: CourseExportCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    export = create_course_export(db, current_user, project_id, payload)
    background_tasks.add_task(run_course_export_job, export.id, current_user.id, project_id)
    return {"success": True, "data": export_to_response(export)}


@router.get("")
def get_course_exports(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    exports = list_course_exports(db, current_user, project_id)
    return {"success": True, "data": [export_to_response(export) for export in exports]}


@router.get("/{export_id}")
def get_course_export_detail(
    project_id: UUID,
    export_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    export = get_course_export(db, current_user, project_id, export_id)
    return {"success": True, "data": export_to_response(export)}


@router.get("/{export_id}/download")
def download_course_export(
    project_id: UUID,
    export_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    export, file_path = get_course_export_download_path(db, current_user, project_id, export_id)
    filename = file_path.name
    return FileResponse(path=file_path, media_type="application/zip", filename=filename)


@router.delete("/{export_id}")
def delete_course_export_endpoint(
    project_id: UUID,
    export_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    delete_course_export(db, current_user, project_id, export_id)
    return {"success": True, "data": {"message": "Exportacao excluida com sucesso."}}
