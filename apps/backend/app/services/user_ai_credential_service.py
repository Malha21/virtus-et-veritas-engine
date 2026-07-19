from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.user import User
from app.models.user_ai_credential import UserAICredential
from app.providers.ai import PROVIDER_KEYS


def _validate_provider_type(provider_type: str) -> None:
    if provider_type not in PROVIDER_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provedor de IA inválido.",
        )


def list_user_credentials(db: Session, user: User) -> list[UserAICredential]:
    statement = select(UserAICredential).where(UserAICredential.user_id == user.id)
    return list(db.execute(statement).scalars().all())


def get_user_credential(db: Session, user: User, provider_type: str) -> UserAICredential | None:
    statement = select(UserAICredential).where(
        UserAICredential.user_id == user.id,
        UserAICredential.provider_type == provider_type,
    )
    return db.execute(statement).scalar_one_or_none()


def upsert_user_credential(db: Session, user: User, provider_type: str, api_key: str) -> UserAICredential:
    _validate_provider_type(provider_type)
    api_key = api_key.strip()

    credential = get_user_credential(db, user, provider_type)
    if credential is None:
        credential = UserAICredential(user_id=user.id, provider_type=provider_type)

    credential.encrypted_api_key = encrypt_secret(api_key)
    credential.key_last_four = api_key[-4:]
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential


def delete_user_credential(db: Session, user: User, provider_type: str) -> None:
    credential = get_user_credential(db, user, provider_type)
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma chave cadastrada para este provedor.",
        )
    db.delete(credential)
    db.commit()


def get_decrypted_key_for_user(db: Session, user_id: UUID, provider_type: str) -> str | None:
    statement = select(UserAICredential).where(
        UserAICredential.user_id == user_id,
        UserAICredential.provider_type == provider_type,
    )
    credential = db.execute(statement).scalar_one_or_none()
    if credential is None:
        return None
    return decrypt_secret(credential.encrypted_api_key)


def resolve_generation_api_key(db: Session, current_user: User, provider_type: str) -> str | None:
    """Resolve a chave a usar para uma geracao de IA.

    Retorna a chave pessoal do usuario, se cadastrada. Se nao houver chave
    pessoal: admins continuam usando o fallback global do .env (retorna
    None, o provider entende isso como "usar settings.<provider>_api_key");
    usuarios comuns sao bloqueados e devem cadastrar a propria chave antes
    de gerar conteudo - nenhum uso de outro usuario deve cair na conta do
    administrador sem que ele opte por isso explicitamente.
    """
    personal_key = get_decrypted_key_for_user(db, current_user.id, provider_type)
    if personal_key is not None:
        return personal_key

    if current_user.role == "admin":
        return None

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Cadastre sua chave de API para {provider_type} em "
            "Minhas APIs antes de gerar conteúdo com IA."
        ),
    )
