import base64
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.video.base import ProviderAsset, ProviderVideoJob, ProviderVideoStatus, VideoProviderError


def require_api_key(settings: Settings) -> str:
    if not settings.did_api_key:
        raise VideoProviderError("DID_API_KEY não configurada no servidor.")
    return settings.did_api_key


def get_api_base_url(settings: Settings) -> str:
    return (settings.did_api_base_url or "https://api.d-id.com").rstrip("/")


def auth_header(api_key: str) -> str:
    encoded = base64.b64encode(api_key.encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def safe_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        return response.json()
    except ValueError:
        return None


def extract_error_message(response: httpx.Response) -> str:
    payload = safe_json(response)
    if isinstance(payload, dict):
        message = payload.get("description") or payload.get("message")
        if message:
            return str(message)
    return f"D-ID retornou um erro inesperado (HTTP {response.status_code})."


def upload_audio_asset(audio_path: Path, settings: Settings, timeout: float = 60.0) -> ProviderAsset:
    api_key = require_api_key(settings)
    if not audio_path.exists() or not audio_path.is_file():
        raise VideoProviderError("Arquivo de áudio de origem não encontrado.")

    url = f"{get_api_base_url(settings)}/audios"
    headers = {"Authorization": auth_header(api_key)}
    mime_type = mimetypes.guess_type(audio_path.name)[0] or "audio/mpeg"

    try:
        with audio_path.open("rb") as file_obj:
            response = httpx.post(
                url,
                headers=headers,
                files={"audio": (audio_path.name, file_obj, mime_type)},
                timeout=timeout,
            )
    except httpx.HTTPError as exc:
        raise VideoProviderError("Não foi possível conectar à D-ID para enviar o áudio.") from exc

    if response.status_code >= 400:
        raise VideoProviderError(
            extract_error_message(response),
            status_code=response.status_code,
            raw_response=safe_json(response),
        )

    payload = safe_json(response) or {}
    audio_url = payload.get("url")
    if not audio_url:
        raise VideoProviderError("D-ID não retornou uma URL para o áudio enviado.", raw_response=payload)

    return ProviderAsset(asset_id=None, url=audio_url, raw_response=payload)


def create_talk(
    source_image_url: str,
    audio_url: str,
    settings: Settings,
    title: str | None = None,
    timeout: float = 30.0,
) -> ProviderVideoJob:
    api_key = require_api_key(settings)
    if not source_image_url:
        raise VideoProviderError("Informe source_image_url ou configure DID_DEFAULT_SOURCE_IMAGE_URL.")

    url = f"{get_api_base_url(settings)}/talks"
    headers = {"Authorization": auth_header(api_key), "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "source_url": source_image_url,
        "script": {
            "type": "audio",
            "audio_url": audio_url,
        },
    }
    if title:
        body["name"] = title

    try:
        response = httpx.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        raise VideoProviderError("Não foi possível conectar à D-ID para criar o vídeo.") from exc

    if response.status_code >= 400:
        raise VideoProviderError(
            extract_error_message(response),
            status_code=response.status_code,
            raw_response=safe_json(response),
        )

    payload = safe_json(response) or {}
    talk_id = payload.get("id")
    if not talk_id:
        raise VideoProviderError("D-ID não retornou um id para o vídeo criado.", raw_response=payload)

    return ProviderVideoJob(job_id=talk_id, status=payload.get("status") or "created", raw_response=payload)


def get_talk_status(talk_id: str, settings: Settings, timeout: float = 30.0) -> ProviderVideoStatus:
    api_key = require_api_key(settings)
    url = f"{get_api_base_url(settings)}/talks/{talk_id}"
    headers = {"Authorization": auth_header(api_key)}

    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise VideoProviderError("Não foi possível conectar à D-ID para consultar o status do vídeo.") from exc

    if response.status_code >= 400:
        raise VideoProviderError(
            extract_error_message(response),
            status_code=response.status_code,
            raw_response=safe_json(response),
        )

    payload = safe_json(response) or {}
    status_value = payload.get("status") or "created"
    failure_message = None
    if status_value in {"error", "rejected"}:
        error_obj = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        failure_message = (
            error_obj.get("description") or payload.get("description") or "Falha ao gerar vídeo na D-ID."
        )

    return ProviderVideoStatus(
        job_id=payload.get("id") or talk_id,
        status=status_value,
        video_url=payload.get("result_url"),
        duration=payload.get("duration"),
        failure_message=failure_message,
        raw_response=payload,
    )


def download_video(video_url: str, destination: Path, timeout: float = 120.0) -> None:
    try:
        with httpx.stream("GET", video_url, timeout=timeout) as response:
            if response.status_code >= 400:
                raise VideoProviderError(f"Não foi possível baixar o vídeo final da D-ID (HTTP {response.status_code}).")
            with destination.open("wb") as file_obj:
                for chunk in response.iter_bytes():
                    file_obj.write(chunk)
    except httpx.HTTPError as exc:
        destination.unlink(missing_ok=True)
        raise VideoProviderError("Não foi possível baixar o vídeo final da D-ID.") from exc
