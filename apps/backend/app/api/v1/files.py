from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.file import ProjectFileResponse
from app.services.file_service import list_project_files, save_project_file

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])


@router.post("")
def upload_project_file(
    project_id: UUID,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    project_file = save_project_file(db, current_user, project_id, file)
    data = ProjectFileResponse.model_validate(project_file)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("")
def get_project_files(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    files = list_project_files(db, current_user, project_id)
    data = [ProjectFileResponse.model_validate(item).model_dump(mode="json") for item in files]
    return {"success": True, "data": data}
