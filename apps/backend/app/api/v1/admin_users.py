from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import AdminUserCreate, AdminUserResponse
from app.services.user_service import (
    create_user_in_organization,
    list_users_in_organization,
    set_user_status,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("")
def get_users(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
) -> dict[str, object]:
    users = list_users_in_organization(db, current_user.organization_id)
    data = [AdminUserResponse.model_validate(item).model_dump(mode="json") for item in users]
    return {"success": True, "data": data}


@router.post("")
def create_user(
    payload: AdminUserCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
) -> dict[str, object]:
    user = create_user_in_organization(db, current_user.organization_id, payload)
    data = AdminUserResponse.model_validate(user)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/{user_id}/deactivate")
def deactivate_user(
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
) -> dict[str, object]:
    user = set_user_status(db, current_user.organization_id, user_id, current_user.id, "inactive")
    data = AdminUserResponse.model_validate(user)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.post("/{user_id}/reactivate")
def reactivate_user(
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
) -> dict[str, object]:
    user = set_user_status(db, current_user.organization_id, user_id, current_user.id, "active")
    data = AdminUserResponse.model_validate(user)
    return {"success": True, "data": data.model_dump(mode="json")}
