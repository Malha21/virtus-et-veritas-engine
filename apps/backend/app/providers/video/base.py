from dataclasses import dataclass
from typing import Any


class VideoProviderError(Exception):
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
class ProviderAsset:
    asset_id: str | None
    url: str | None
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class ProviderVideoJob:
    job_id: str
    status: str
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class ProviderVideoStatus:
    job_id: str
    status: str
    video_url: str | None
    duration: float | None
    failure_message: str | None
    raw_response: dict[str, Any]
