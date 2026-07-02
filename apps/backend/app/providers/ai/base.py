from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class AIProviderRequest:
    system_prompt: str
    user_prompt: str
    response_format: str = "json"
    temperature: float = 0.3
    model: str | None = None


@dataclass
class AIProviderResponse:
    success: bool
    content: str | None = None
    raw_response: dict[str, Any] | None = None
    usage: dict[str, int | None] = field(default_factory=dict)
    error: str | None = None


class AIProvider(Protocol):
    def generate_text(self, request: AIProviderRequest) -> AIProviderResponse:
        ...
