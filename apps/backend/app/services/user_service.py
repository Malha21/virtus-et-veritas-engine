from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.user import User


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
