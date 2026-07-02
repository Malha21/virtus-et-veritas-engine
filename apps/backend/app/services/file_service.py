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


def _validate_pdf_upload(file: UploadFile) -> None:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nesta fase, apenas arquivos PDF são aceitos.",
        )

    if file.content_type and file.content_type not in ALLOWED_PDF_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo enviado não parece ser um PDF válido.",
        )


def _copy_upload_to_temp(file: UploadFile, max_size_bytes: int) -> tuple[Path, int, str]:
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
                    detail="O PDF excede o tamanho máximo permitido.",
                )
            checksum.update(chunk)
            temp_file.write(chunk)

    if total_size == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo PDF está vazio.",
        )

    with temp_path.open("rb") as temp_file:
        if temp_file.read(4) != b"%PDF":
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O arquivo enviado não possui assinatura de PDF válida.",
            )

    return temp_path, total_size, checksum.hexdigest()


def save_project_pdf(db: Session, current_user: User, project_id: uuid.UUID, file: UploadFile) -> ProjectFile:
    settings = get_settings()
    project = get_project_by_id(db, current_user.organization_id, project_id)
    _validate_pdf_upload(file)

    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    temp_path, file_size, checksum = _copy_upload_to_temp(file, max_size_bytes)

    original_filename = Path(file.filename or "arquivo.pdf").name
    stored_filename = f"{uuid.uuid4()}.pdf"
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

    project_file = ProjectFile(
        project_id=project.id,
        organization_id=current_user.organization_id,
        file_type="source_pdf",
        original_filename=original_filename,
        storage_path=storage_path,
        mime_type=file.content_type or "application/pdf",
        file_size=file_size,
        checksum=checksum,
        status="uploaded",
    )
    db.add(project_file)
    db.commit()
    db.refresh(project_file)
    return project_file


def list_project_files(db: Session, current_user: User, project_id: uuid.UUID) -> list[ProjectFile]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    statement = (
        select(ProjectFile)
        .where(
            ProjectFile.project_id == project.id,
            ProjectFile.organization_id == current_user.organization_id,
        )
        .order_by(ProjectFile.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())
