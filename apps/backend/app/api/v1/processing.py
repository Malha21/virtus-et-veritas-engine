from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.processing import ProcessingLogResponse, ProcessingStatusResponse, StartProcessingResponse
from app.services.processing_service import get_processing_status, list_processing_logs, start_text_extraction

router = APIRouter(prefix="/projects/{project_id}", tags=["processing"])


@router.post("/process")
def process_project(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    job = start_text_extraction(db, current_user, project_id)
    message = "Texto extraído com sucesso" if job.status == "completed" else "Falha ao extrair texto do PDF"
    data = StartProcessingResponse(
        project_id=job.project_id,
        processing_status="text_extracted" if job.status == "completed" else "failed",
        message=message,
        job_id=job.id,
    )
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/status")
def project_processing_status(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    data = ProcessingStatusResponse(**get_processing_status(db, current_user, project_id))
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/logs")
def project_processing_logs(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    logs = list_processing_logs(db, current_user, project_id)
    data = [ProcessingLogResponse.model_validate(log).model_dump(mode="json") for log in logs]
    return {"success": True, "data": data}
