from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from app.core.config import get_settings


@lru_cache
def _get_fernet() -> Fernet:
    settings = get_settings()
    if not settings.api_encryption_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_ENCRYPTION_KEY não configurada no servidor.",
        )
    return Fernet(settings.api_encryption_key.encode("utf-8"))


def encrypt_secret(plain_text: str) -> str:
    return _get_fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_text: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível decifrar a chave armazenada.",
        ) from exc
