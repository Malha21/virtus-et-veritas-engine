import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings

HEYGEN_RESOLUTIONS = {"720p", "1080p", "4k"}


class HeyGenAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.raw_response = raw_response


@dataclass(frozen=True)
class HeyGenAsset:
    asset_id: str
    url: str | None
    mime_type: str | None
    size_bytes: int | None
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class HeyGenVideoJob:
    video_id: str
    status: str
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class HeyGenVideoStatus:
    video_id: str
    status: str
    video_url: str | None
    duration: float | None
    failure_message: str | None
    raw_response: dict[str, Any]


def require_api_key(settings: Settings) -> str:
    if not settings.heygen_api_key:
        raise HeyGenAPIError("HEYGEN_API_KEY não configurada no servidor.")
    return settings.heygen_api_key


def get_api_base_url(settings: Settings) -> str:
    return (settings.heygen_api_base_url or "https://api.heygen.com").rstrip("/")


def safe_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        return response.json()
    except ValueError:
        return None


def extract_error_message(response: httpx.Response) -> str:
    payload = safe_json(response)
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return f"HeyGen retornou um erro inesperado (HTTP {response.status_code})."


def upload_audio_asset(audio_path: Path, settings: Settings, timeout: float = 60.0) -> HeyGenAsset:
    api_key = require_api_key(settings)
    if not audio_path.exists() or not audio_path.is_file():
        raise HeyGenAPIError("Arquivo de áudio de origem não encontrado.")

    url = f"{get_api_base_url(settings)}/v3/assets"
    headers = {"x-api-key": api_key}
    mime_type = mimetypes.guess_type(audio_path.name)[0] or "audio/mpeg"

    try:
        with audio_path.open("rb") as file_obj:
            response = httpx.post(
                url,
                headers=headers,
                files={"file": (audio_path.name, file_obj, mime_type)},
                timeout=timeout,
            )
    except httpx.HTTPError as exc:
        raise HeyGenAPIError("Não foi possível conectar à HeyGen para enviar o áudio.") from exc

    if response.status_code >= 400:
        raise HeyGenAPIError(
            extract_error_message(response),
            status_code=response.status_code,
            raw_response=safe_json(response),
        )

    payload = safe_json(response) or {}
    data = payload.get("data") or {}
    if not data.get("asset_id"):
        raise HeyGenAPIError("HeyGen não retornou um asset_id para o áudio enviado.", raw_response=payload)

    return HeyGenAsset(
        asset_id=data["asset_id"],
        url=data.get("url"),
        mime_type=data.get("mime_type"),
        size_bytes=data.get("size_bytes"),
        raw_response=payload,
    )


def create_heygen_video(
    avatar_id: str,
    audio_asset_id: str,
    resolution: str,
    settings: Settings,
    title: str | None = None,
    timeout: float = 30.0,
) -> HeyGenVideoJob:
    api_key = require_api_key(settings)
    if not avatar_id:
        raise HeyGenAPIError("avatar_id da HeyGen não informado.")

    url = f"{get_api_base_url(settings)}/v3/videos"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    normalized_resolution = (resolution or "").lower().strip()
    heygen_resolution = normalized_resolution if normalized_resolution in HEYGEN_RESOLUTIONS else "1080p"

    body: dict[str, Any] = {
        "type": "avatar",
        "avatar_id": avatar_id,
        "audio_asset_id": audio_asset_id,
        "resolution": heygen_resolution,
        "output_format": "mp4",
    }
    if title:
        body["title"] = title

    try:
        response = httpx.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        raise HeyGenAPIError("Não foi possível conectar à HeyGen para criar o vídeo.") from exc

    if response.status_code >= 400:
        raise HeyGenAPIError(
            extract_error_message(response),
            status_code=response.status_code,
            raw_response=safe_json(response),
        )

    payload = safe_json(response) or {}
    data = payload.get("data") or {}
    if not data.get("video_id"):
        raise HeyGenAPIError("HeyGen não retornou um video_id para o job criado.", raw_response=payload)

    return HeyGenVideoJob(
        video_id=data["video_id"],
        status=data.get("status") or "pending",
        raw_response=payload,
    )


def get_heygen_video_status(video_id: str, settings: Settings, timeout: float = 30.0) -> HeyGenVideoStatus:
    api_key = require_api_key(settings)
    url = f"{get_api_base_url(settings)}/v3/videos/{video_id}"
    headers = {"x-api-key": api_key}

    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise HeyGenAPIError("Não foi possível conectar à HeyGen para consultar o status do vídeo.") from exc

    if response.status_code >= 400:
        raise HeyGenAPIError(
            extract_error_message(response),
            status_code=response.status_code,
            raw_response=safe_json(response),
        )

    payload = safe_json(response) or {}
    data = payload.get("data") or {}
    status = data.get("status") or "processing"
    failure_message = None
    if status == "failed":
        failure_message = data.get("failure_message") or data.get("error")

    return HeyGenVideoStatus(
        video_id=data.get("id") or video_id,
        status=status,
        video_url=data.get("video_url"),
        duration=data.get("duration"),
        failure_message=failure_message,
        raw_response=payload,
    )


def download_heygen_video(video_url: str, destination: Path, timeout: float = 120.0) -> None:
    try:
        with httpx.stream("GET", video_url, timeout=timeout) as response:
            if response.status_code >= 400:
                raise HeyGenAPIError(f"Não foi possível baixar o vídeo final da HeyGen (HTTP {response.status_code}).")
            with destination.open("wb") as file_obj:
                for chunk in response.iter_bytes():
                    file_obj.write(chunk)
    except httpx.HTTPError as exc:
        destination.unlink(missing_ok=True)
        raise HeyGenAPIError("Não foi possível baixar o vídeo final da HeyGen.") from exc
