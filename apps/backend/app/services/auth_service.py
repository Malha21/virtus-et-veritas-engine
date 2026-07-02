from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.services.user_service import get_user_by_email


def authenticate_user(db: Session, credentials: LoginRequest) -> User:
    user = get_user_by_email(db, credentials.email)
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo.",
        )

    user.last_login_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_login_token(user: User) -> str:
    return create_access_token(
        subject=str(user.id),
        extra_claims={
            "organization_id": str(user.organization_id),
            "role": user.role,
        },
    )
