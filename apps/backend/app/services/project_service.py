import re
import unicodedata
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate

PROJECT_RETENTION_DAYS = 10
HIDDEN_PROJECT_STATUSES = {"archived", "expired", "deleted"}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "projeto"


def generate_unique_slug(db: Session, organization_id: UUID, title: str) -> str:
    base_slug = slugify(title)
    slug = base_slug
    counter = 2

    while db.execute(
        select(Project.id).where(
            Project.organization_id == organization_id,
            Project.slug == slug,
        )
    ).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def create_project(db: Session, current_user: User, payload: ProjectCreate) -> Project:
    created_at = datetime.now(UTC)
    project = Project(
        organization_id=current_user.organization_id,
        owner_id=current_user.id,
        title=payload.title,
        slug=generate_unique_slug(db, current_user.organization_id, payload.title),
        product_type=payload.product_type,
        target_audience=payload.target_audience,
        tone_of_voice=payload.tone_of_voice,
        desired_duration=payload.desired_duration,
        description=payload.description,
        ai_provider=payload.ai_provider,
        status="active",
        processing_status="draft",
        created_at=created_at,
        updated_at=created_at,
        expires_at=created_at + timedelta(days=PROJECT_RETENTION_DAYS),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(
    db: Session,
    organization_id: UUID,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
    product_type: str | None = None,
    processing_status: str | None = None,
    search: str | None = None,
) -> tuple[list[Project], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    filters = [
        Project.organization_id == organization_id,
        Project.archived_at.is_(None),
        Project.deleted_at.is_(None),
        Project.status.not_in(HIDDEN_PROJECT_STATUSES),
    ]
    if status_filter:
        filters.append(Project.status == status_filter)
    if product_type:
        filters.append(Project.product_type == product_type)
    if processing_status:
        filters.append(Project.processing_status == processing_status)
    if search:
        search_value = f"%{search}%"
        filters.append(
            or_(
                Project.title.ilike(search_value),
                Project.description.ilike(search_value),
            )
        )

    total = db.execute(select(func.count()).select_from(Project).where(*filters)).scalar_one()
    statement = (
        select(Project)
        .where(*filters)
        .order_by(Project.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.execute(statement).scalars().all()), total


def get_project_by_id(db: Session, organization_id: UUID, project_id: UUID) -> Project:
    project = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
            Project.status.not_in(HIDDEN_PROJECT_STATUSES),
            Project.archived_at.is_(None),
            Project.deleted_at.is_(None),
        )
    ).scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projeto não encontrado.",
        )

    return project


def update_project(
    db: Session,
    organization_id: UUID,
    project_id: UUID,
    payload: ProjectUpdate,
) -> Project:
    project = get_project_by_id(db, organization_id, project_id)
    updates = payload.model_dump(exclude_unset=True)

    if "title" in updates and updates["title"] and updates["title"] != project.title:
        project.slug = generate_unique_slug(db, organization_id, updates["title"])

    for field, value in updates.items():
        setattr(project, field, value)

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def archive_project(db: Session, organization_id: UUID, project_id: UUID) -> None:
    project = db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
            Project.deleted_at.is_(None),
        )
    ).scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projeto nÃ£o encontrado.",
        )

    project.status = "archived"
    project.archived_at = datetime.now(UTC)
    db.add(project)
    db.commit()
