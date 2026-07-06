import base64
import hashlib
import hmac
import time
from uuid import UUID

from app.core.config import Settings, get_settings

PUBLIC_AUDIO_URL_TTL_SECONDS = 45 * 60


class SignedTokenError(Exception):
    pass


def _signing_secret(settings: Settings | None = None) -> bytes:
    active_settings = settings or get_settings()
    return active_settings.jwt_secret.encode("utf-8")


def _sign_payload(payload: str, settings: Settings | None = None) -> str:
    digest = hmac.new(_signing_secret(settings), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def generate_audio_asset_token(
    audio_id: UUID,
    ttl_seconds: int = PUBLIC_AUDIO_URL_TTL_SECONDS,
    settings: Settings | None = None,
) -> str:
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{audio_id}:{expires_at}"
    payload_b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    signature = _sign_payload(payload, settings)
    return f"{payload_b64}.{signature}"


def verify_audio_asset_token(token: str, settings: Settings | None = None) -> UUID:
    try:
        payload_b64, signature = token.split(".", 1)
        padding = "=" * (-len(payload_b64) % 4)
        payload = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
        audio_id_str, expires_at_str = payload.rsplit(":", 1)
    except (ValueError, UnicodeDecodeError) as exc:
        raise SignedTokenError("Token inválido.") from exc

    expected_signature = _sign_payload(payload, settings)
    if not hmac.compare_digest(signature, expected_signature):
        raise SignedTokenError("Assinatura do token inválida.")

    if int(expires_at_str) < int(time.time()):
        raise SignedTokenError("Token expirado.")

    try:
        return UUID(audio_id_str)
    except ValueError as exc:
        raise SignedTokenError("Token inválido.") from exc
