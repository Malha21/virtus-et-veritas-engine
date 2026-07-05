from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.audio import AudioGenerateRequest
from app.services.audio_service import (
    audio_to_response_data,
    delete_project_audio,
    export_project_audios_zip,
    generate_tts_audio,
    get_audio_download_path,
    get_audio_media_type,
    list_project_audios,
)

router = APIRouter(prefix="/projects/{project_id}/audio", tags=["audio"])


@router.post("/generate")
def post_generate_audio(
    project_id: UUID,
    payload: AudioGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    audio = generate_tts_audio(db, current_user, project_id, payload)
    return {"success": True, "data": audio_to_response_data(audio)}


@router.get("")
def get_project_audios(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    audios = list_project_audios(db, current_user, project_id)
    return {"success": True, "data": [audio_to_response_data(audio) for audio in audios]}


@router.get("/export.zip")
def export_audios_zip(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    scope: str = Query(default="all", pattern="^(lesson|module|all)$"),
    generated_content_id: UUID | None = None,
    module_number: int | None = None,
    title_contains: str | None = None,
) -> Response:
    export = export_project_audios_zip(
        db=db,
        current_user=current_user,
        project_id=project_id,
        scope=scope,
        generated_content_id=generated_content_id,
        module_number=module_number,
        title_contains=title_contains,
    )
    return Response(
        content=export.content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )


@router.get("/{audio_id}/download")
def download_audio(
    project_id: UUID,
    audio_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    audio, file_path = get_audio_download_path(db, current_user, project_id, audio_id)
    filename = f"{audio.title or 'narration-audio'}-{audio.id}.{audio.format}"
    return FileResponse(
        path=file_path,
        media_type=get_audio_media_type(audio.format),
        filename=filename,
    )


@router.delete("/{audio_id}")
def delete_audio(
    project_id: UUID,
    audio_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    delete_project_audio(db, current_user, project_id, audio_id)
    return {"success": True, "data": {"message": "Áudio excluído com sucesso."}}
