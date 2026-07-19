from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import AdminUserCreate


def get_user_by_email(db: Session, email: str) -> User | None:
    statement = (
        select(User)
        .options(selectinload(User.organization))
        .where(User.email == email.lower())
    )
    return db.execute(statement).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    statement = (
        select(User)
        .options(selectinload(User.organization))
        .where(User.id == user_id)
    )
    return db.execute(statement).scalar_one_or_none()


def list_users_in_organization(db: Session, organization_id: UUID) -> list[User]:
    statement = (
        select(User)
        .where(User.organization_id == organization_id)
        .order_by(User.created_at.asc())
    )
    return list(db.execute(statement).scalars().all())


def create_user_in_organization(db: Session, organization_id: UUID, payload: AdminUserCreate) -> User:
    email = payload.email.lower()
    if get_user_by_email(db, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário com este e-mail.",
        )

    user = User(
        organization_id=organization_id,
        name=payload.name,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_in_organization(db: Session, organization_id: UUID, user_id: UUID) -> User:
    user = get_user_by_id(db, user_id)
    if user is None or user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )
    return user


def set_user_status(
    db: Session, organization_id: UUID, user_id: UUID, current_user_id: UUID, new_status: str
) -> User:
    if user_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode alterar o status da sua própria conta.",
        )

    user = get_user_in_organization(db, organization_id, user_id)
    user.status = new_status
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
