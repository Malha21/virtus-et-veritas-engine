from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.video.base import ProviderVideoJob, ProviderVideoStatus, VideoProviderError


def require_api_key(settings: Settings) -> str:
    if not settings.sync_api_key:
        raise VideoProviderError("SYNC_API_KEY não configurada no servidor.")
    return settings.sync_api_key


def get_api_base_url(settings: Settings) -> str:
    return (settings.sync_api_base_url or "https://api.sync.so/v2").rstrip("/")


def safe_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        return response.json()
    except ValueError:
        return None


def extract_error_message(response: httpx.Response) -> str:
    payload = safe_json(response)
    if isinstance(payload, dict) and payload.get("message"):
        return str(payload["message"])
    return f"Sync Labs retornou um erro inesperado (HTTP {response.status_code})."


def create_generation(
    audio_url: str,
    settings: Settings,
    source_video_url: str | None = None,
    source_image_url: str | None = None,
    model: str | None = None,
    timeout: float = 30.0,
) -> ProviderVideoJob:
    api_key = require_api_key(settings)

    resolved_model = model or settings.sync_default_model or "lipsync-2"
    input_items: list[dict[str, Any]] = []
    if source_video_url:
        input_items.append({"type": "video", "url": source_video_url})
    elif source_image_url:
        input_items.append({"type": "image", "url": source_image_url})
        resolved_model = "sync-3"
    else:
        raise VideoProviderError(
            "Informe source_video_url ou source_image_url, ou configure "
            "SYNC_DEFAULT_SOURCE_VIDEO_URL/SYNC_DEFAULT_SOURCE_IMAGE_URL."
        )

    input_items.append({"type": "audio", "url": audio_url})

    url = f"{get_api_base_url(settings)}/generate"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    body = {"model": resolved_model, "input": input_items}

    try:
        response = httpx.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        raise VideoProviderError("Não foi possível conectar à Sync Labs para criar o vídeo.") from exc

    if response.status_code >= 400:
        raise VideoProviderError(
            extract_error_message(response),
            status_code=response.status_code,
            raw_response=safe_json(response),
        )

    payload = safe_json(response) or {}
    generation_id = payload.get("id")
    if not generation_id:
        raise VideoProviderError("Sync Labs não retornou um id para o vídeo criado.", raw_response=payload)

    return ProviderVideoJob(
        job_id=generation_id,
        status=str(payload.get("status") or "PENDING"),
        raw_response=payload,
    )


def get_generation_status(generation_id: str, settings: Settings, timeout: float = 30.0) -> ProviderVideoStatus:
    api_key = require_api_key(settings)
    url = f"{get_api_base_url(settings)}/generate/{generation_id}"
    headers = {"x-api-key": api_key}

    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise VideoProviderError("Não foi possível conectar à Sync Labs para consultar o status do vídeo.") from exc

    if response.status_code >= 400:
        raise VideoProviderError(
            extract_error_message(response),
            status_code=response.status_code,
            raw_response=safe_json(response),
        )

    payload = safe_json(response) or {}
    status_value = str(payload.get("status") or "PENDING").upper()
    failure_message = None
    if status_value in {"FAILED", "REJECTED"}:
        failure_message = payload.get("errorMessage") or payload.get("message") or "Falha ao gerar vídeo na Sync Labs."

    return ProviderVideoStatus(
        job_id=payload.get("id") or generation_id,
        status=status_value,
        video_url=payload.get("outputUrl"),
        duration=payload.get("outputDuration"),
        failure_message=failure_message,
        raw_response=payload,
    )


def download_video(video_url: str, destination: Path, timeout: float = 120.0) -> None:
    try:
        with httpx.stream("GET", video_url, timeout=timeout) as response:
            if response.status_code >= 400:
                raise VideoProviderError(
                    f"Não foi possível baixar o vídeo final da Sync Labs (HTTP {response.status_code})."
                )
            with destination.open("wb") as file_obj:
                for chunk in response.iter_bytes():
                    file_obj.write(chunk)
    except httpx.HTTPError as exc:
        destination.unlink(missing_ok=True)
        raise VideoProviderError("Não foi possível baixar o vídeo final da Sync Labs.") from exc
