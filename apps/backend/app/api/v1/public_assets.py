from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.generated_audio import GeneratedAudio
from app.services.audio_service import get_audio_file_path, get_audio_media_type
from app.services.signed_url_service import SignedTokenError, verify_audio_asset_token

router = APIRouter(prefix="/public", tags=["public-assets"])


@router.get("/audio-assets/{token}")
def get_public_audio_asset(
    token: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        audio_id = verify_audio_asset_token(token)
    except SignedTokenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    audio = db.execute(select(GeneratedAudio).where(GeneratedAudio.id == audio_id)).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Áudio não encontrado.")

    file_path = get_audio_file_path(audio)
    if file_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de áudio não encontrado.")

    return FileResponse(path=file_path, media_type=get_audio_media_type(audio.format))
