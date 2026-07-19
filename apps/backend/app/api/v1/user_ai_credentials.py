from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.project import AIProviderChoice
from app.schemas.user_ai_credential import UserAICredentialResponse, UserAICredentialUpsert
from app.services.user_ai_credential_service import (
    delete_user_credential,
    list_user_credentials,
    upsert_user_credential,
)

router = APIRouter(prefix="/account/api-keys", tags=["account-api-keys"])


@router.get("")
def get_my_api_keys(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    credentials = list_user_credentials(db, current_user)
    data = [UserAICredentialResponse.model_validate(item).model_dump(mode="json") for item in credentials]
    return {"success": True, "data": data}


@router.put("/{provider_type}")
def put_my_api_key(
    provider_type: AIProviderChoice,
    payload: UserAICredentialUpsert,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    credential = upsert_user_credential(db, current_user, provider_type, payload.api_key)
    data = UserAICredentialResponse.model_validate(credential)
    return {"success": True, "data": data.model_dump(mode="json")}


@router.delete("/{provider_type}")
def delete_my_api_key(
    provider_type: AIProviderChoice,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    delete_user_credential(db, current_user, provider_type)
    return {"success": True, "data": {"message": "Chave removida com sucesso."}}
