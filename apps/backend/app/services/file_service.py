import hashlib
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.project_file import ProjectFile
from app.models.user import User
from app.providers.storage.local_storage import LocalStorageProvider
from app.services.project_service import get_project_by_id

ALLOWED_PDF_MIME_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}
ALLOWED_EPUB_MIME_TYPES = {"application/epub+zip", "application/octet-stream"}
SUPPORTED_EXTENSIONS = {".pdf": "source_pdf", ".epub": "source_epub"}


def _resolve_upload_extension(file: UploadFile) -> str:
    filename = (file.filename or "").lower()
    for extension in SUPPORTED_EXTENSIONS:
        if filename.endswith(extension):
            return extension

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Nesta fase, apenas arquivos PDF ou EPUB são aceitos.",
    )


def _validate_document_upload(file: UploadFile, extension: str) -> None:
    if extension == ".pdf" and file.content_type and file.content_type not in ALLOWED_PDF_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo enviado não parece ser um PDF válido.",
        )

    if extension == ".epub" and file.content_type and file.content_type not in ALLOWED_EPUB_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo enviado não parece ser um EPUB válido.",
        )


DOCUMENT_SIGNATURES: dict[str, bytes] = {
    ".pdf": b"%PDF",
    ".epub": b"PK\x03\x04",  # EPUB e um arquivo ZIP
}


def _copy_upload_to_temp(file: UploadFile, max_size_bytes: int, extension: str) -> tuple[Path, int, str]:
    checksum = hashlib.sha256()
    total_size = 0

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        while chunk := file.file.read(1024 * 1024):
            total_size += len(chunk)
            if total_size > max_size_bytes:
                temp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="O arquivo excede o tamanho máximo permitido.",
                )
            checksum.update(chunk)
            temp_file.write(chunk)

    if total_size == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo enviado está vazio.",
        )

    signature = DOCUMENT_SIGNATURES[extension]
    with temp_path.open("rb") as temp_file:
        if temp_file.read(len(signature)) != signature:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"O arquivo enviado não possui assinatura de {extension[1:].upper()} válida.",
            )

    return temp_path, total_size, checksum.hexdigest()


def save_project_file(db: Session, current_user: User, project_id: uuid.UUID, file: UploadFile) -> ProjectFile:
    settings = get_settings()
    project = get_project_by_id(db, current_user, project_id)

    existing_file = db.execute(
        select(ProjectFile).where(ProjectFile.project_id == project.id)
    ).scalar_one_or_none()
    if existing_file is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este projeto já possui um documento-base enviado. Remova o arquivo atual antes de enviar um novo.",
        )

    extension = _resolve_upload_extension(file)
    _validate_document_upload(file, extension)

    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    temp_path, file_size, checksum = _copy_upload_to_temp(file, max_size_bytes, extension)

    original_filename = Path(file.filename or f"arquivo{extension}").name
    stored_filename = f"{uuid.uuid4()}{extension}"
    relative_path = Path(
        "organizations",
        str(current_user.organization_id),
        "projects",
        str(project.id),
        "source",
        stored_filename,
    )

    storage = LocalStorageProvider(settings.storage_path)
    try:
        with temp_path.open("rb") as temp_file:
            storage_path = storage.save_file(temp_file, relative_path)
    finally:
        temp_path.unlink(missing_ok=True)
        file.file.seek(0)

    default_mime = "application/pdf" if extension == ".pdf" else "application/epub+zip"
    project_file = ProjectFile(
        project_id=project.id,
        organization_id=current_user.organization_id,
        file_type=SUPPORTED_EXTENSIONS[extension],
        original_filename=original_filename,
        storage_path=storage_path,
        mime_type=file.content_type or default_mime,
        file_size=file_size,
        checksum=checksum,
        status="uploaded",
    )
    project.processing_status = "uploaded"
    db.add(project_file)
    db.add(project)
    db.commit()
    db.refresh(project_file)
    return project_file


def list_project_files(db: Session, current_user: User, project_id: uuid.UUID) -> list[ProjectFile]:
    project = get_project_by_id(db, current_user, project_id)
    statement = (
        select(ProjectFile)
        .where(
            ProjectFile.project_id == project.id,
            ProjectFile.organization_id == current_user.organization_id,
        )
        .order_by(ProjectFile.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def delete_project_file(db: Session, current_user: User, project_id: uuid.UUID, file_id: uuid.UUID) -> None:
    settings = get_settings()
    project = get_project_by_id(db, current_user, project_id)
    project_file = db.execute(
        select(ProjectFile).where(
            ProjectFile.id == file_id,
            ProjectFile.project_id == project.id,
            ProjectFile.organization_id == current_user.organization_id,
        )
    ).scalar_one_or_none()
    if project_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")

    storage_root = Path(settings.storage_path).resolve()
    file_path = (storage_root / project_file.storage_path).resolve()
    if storage_root in file_path.parents and file_path.exists() and file_path.is_file():
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass

    db.delete(project_file)
    db.commit()
