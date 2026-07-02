from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import CurrentUserResponse
from app.services.auth_service import authenticate_user, create_login_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(
    credentials: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    user = authenticate_user(db, credentials)
    token = create_login_token(user)
    data = TokenResponse(access_token=token, user=user)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/me")
def me(current_user: Annotated[User, Depends(get_current_user)]) -> dict[str, object]:
    data = CurrentUserResponse.model_validate(current_user)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/logout")
def logout() -> dict[str, object]:
    return {"success": True, "data": {"message": "Logout realizado com sucesso"}}
