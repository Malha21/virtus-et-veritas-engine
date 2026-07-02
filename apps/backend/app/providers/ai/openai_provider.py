from typing import Any

from openai import OpenAI

from app.core.config import Settings
from app.providers.ai.base import AIProviderRequest, AIProviderResponse


class OpenAIProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_text(self, request: AIProviderRequest) -> AIProviderResponse:
        try:
            if not self.settings.openai_api_key or self.settings.openai_api_key == "change_me_openai_api_key":
                return AIProviderResponse(
                    success=False,
                    error="OPENAI_API_KEY nÃ£o configurada.",
                )

            client = OpenAI(api_key=self.settings.openai_api_key)
            response_format: dict[str, str] | None = None
            if request.response_format == "json":
                response_format = {"type": "json_object"}

            response = client.chat.completions.create(
                model=request.model or self.settings.openai_default_model,
                temperature=request.temperature,
                response_format=response_format,
                messages=[
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
            )
            content = response.choices[0].message.content if response.choices else None
            usage = response.usage
            raw_response: dict[str, Any] | None = None
            if hasattr(response, "model_dump"):
                raw_response = response.model_dump()

            return AIProviderResponse(
                success=True,
                content=content,
                raw_response=raw_response,
                usage={
                    "input_tokens": usage.prompt_tokens if usage else None,
                    "output_tokens": usage.completion_tokens if usage else None,
                },
            )
        except Exception as exc:
            return AIProviderResponse(success=False, error=str(exc))
