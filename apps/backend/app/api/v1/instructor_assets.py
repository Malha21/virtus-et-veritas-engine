import uuid
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.instructor_asset import InstructorAsset
from app.models.instructor_profile import InstructorProfile
from app.models.user import User
from app.schemas.instructor_asset import InstructorAssetResponse, InstructorAssetUpdate

router = APIRouter(prefix="/instructor-assets", tags=["instructor-assets"])

ASSET_TYPES = {"voice_sample", "avatar_image"}
VOICE_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".webm"}
VOICE_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/webm",
}
AVATAR_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_VOICE_BYTES = 25 * 1024 * 1024
MAX_AVATAR_BYTES = 10 * 1024 * 1024
EXTENSIONS_BY_MIME = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/webm": ".webm",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def validate_asset_type(asset_type: str) -> str:
    if asset_type not in ASSET_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de arquivo do instrutor inválido.")
    return asset_type


def asset_to_response(asset: InstructorAsset) -> dict[str, object]:
    data = InstructorAssetResponse.model_validate(asset).model_dump(mode="json")
    data["download_url"] = f"/api/v1/instructor-assets/{asset.id}/download"
    return data


def get_profile_for_upload(db: Session, current_user: User) -> InstructorProfile:
    profile = db.execute(
        select(InstructorProfile).where(InstructorProfile.user_id == current_user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Crie seu Perfil do Instrutor antes de enviar arquivos.",
        )
    return profile


def get_asset_for_user(db: Session, current_user: User, asset_id: UUID) -> InstructorAsset:
    asset = db.execute(
        select(InstructorAsset).where(
            InstructorAsset.id == asset_id,
            InstructorAsset.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo do instrutor não encontrado.")
    return asset


def get_assets_storage_dir(user_id: UUID, asset_type: str) -> Path:
    folder = "voice" if asset_type == "voice_sample" else "avatar"
    path = Path(get_settings().storage_path) / "instructor-assets" / str(user_id) / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_upload(
    asset_type: str,
    mime_type: str | None,
    content: bytes,
    consent_confirmed: bool,
    original_filename: str | None,
) -> str:
    if not consent_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirme que você possui autorização expressa antes de enviar o arquivo.",
        )
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio não pode ser enviado.")

    if asset_type == "voice_sample":
        original_extension = Path(original_filename or "").suffix.lower()
        has_allowed_extension = original_extension in VOICE_EXTENSIONS
        if mime_type == "application/octet-stream":
            if not has_allowed_extension:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de áudio inválido.")
        elif mime_type not in VOICE_MIME_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de áudio inválido.")
        if len(content) > MAX_VOICE_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amostra de voz excede 25 MB.")
        return original_extension if has_allowed_extension else EXTENSIONS_BY_MIME.get(mime_type or "", ".bin")
    else:
        if mime_type not in AVATAR_MIME_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de imagem inválido.")
        if len(content) > MAX_AVATAR_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Imagem do avatar excede 10 MB.")

    return EXTENSIONS_BY_MIME.get(mime_type or "", ".bin")


def safe_download_path(asset: InstructorAsset) -> Path:
    base_dir = (Path(get_settings().storage_path) / "instructor-assets").resolve()
    file_path = Path(asset.file_path).resolve()
    if base_dir != file_path and base_dir not in file_path.parents:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Caminho de arquivo inválido.")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo físico não encontrado.")
    return file_path


@router.get("")
def list_instructor_assets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    asset_type: str | None = Query(default=None),
) -> dict[str, object]:
    filters = [InstructorAsset.user_id == current_user.id]
    if asset_type:
        filters.append(InstructorAsset.asset_type == validate_asset_type(asset_type))

    assets = list(
        db.execute(
            select(InstructorAsset).where(*filters).order_by(InstructorAsset.created_at.desc())
        )
        .scalars()
        .all()
    )
    return {"success": True, "data": [asset_to_response(asset) for asset in assets]}


@router.post("/upload")
async def upload_instructor_asset(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: Annotated[UploadFile, File()],
    asset_type: Annotated[str, Form()],
    consent_confirmed: Annotated[bool, Form()],
    description: Annotated[str | None, Form()] = None,
) -> dict[str, object]:
    valid_asset_type = validate_asset_type(asset_type)
    profile = get_profile_for_upload(db, current_user)
    content = await file.read()
    extension = validate_upload(valid_asset_type, file.content_type, content, consent_confirmed, file.filename)
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    storage_dir = get_assets_storage_dir(current_user.id, valid_asset_type)
    file_path = storage_dir / stored_filename
    file_path.write_bytes(content)

    asset = InstructorAsset(
        user_id=current_user.id,
        instructor_profile_id=profile.id,
        asset_type=valid_asset_type,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=str(file_path),
        mime_type=file.content_type,
        size_bytes=len(content),
        description=description,
        consent_confirmed=consent_confirmed,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {"success": True, "data": asset_to_response(asset)}


@router.put("/{asset_id}")
def update_instructor_asset(
    asset_id: UUID,
    payload: InstructorAssetUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    asset = get_asset_for_user(db, current_user, asset_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(asset, field, value)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {"success": True, "data": asset_to_response(asset)}


@router.delete("/{asset_id}")
def delete_instructor_asset(
    asset_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    asset = get_asset_for_user(db, current_user, asset_id)
    try:
        file_path = safe_download_path(asset)
        file_path.unlink(missing_ok=True)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
    db.delete(asset)
    db.commit()
    return {"success": True, "data": {"message": "Arquivo do instrutor excluído com sucesso."}}


@router.get("/{asset_id}/download")
def download_instructor_asset(
    asset_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    asset = get_asset_for_user(db, current_user, asset_id)
    file_path = safe_download_path(asset)
    return FileResponse(
        path=file_path,
        media_type=asset.mime_type or "application/octet-stream",
        filename=Path(asset.original_filename).name if asset.original_filename else asset.stored_filename,
    )
