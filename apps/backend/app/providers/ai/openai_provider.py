import time
from typing import Any

from openai import OpenAI

from app.core.config import Settings
from app.providers.ai.base import AIProviderRequest, AIProviderResponse


class OpenAIProvider:
    def __init__(self, settings: Settings, api_key: str | None = None) -> None:
        self.settings = settings
        self.api_key = api_key or settings.openai_api_key

    def generate_text(self, request: AIProviderRequest) -> AIProviderResponse:
        if not self.api_key or self.api_key == "change_me_openai_api_key":
            return AIProviderResponse(
                success=False,
                error="OPENAI_API_KEY nÃ£o configurada.",
                provider_name=self.settings.openai_provider_name,
                model_name=request.model or self.settings.openai_default_model,
            )

        attempts = max(request.max_retries, 0) + 1
        last_error: str | None = None

        for attempt in range(1, attempts + 1):
            try:
                return self._call(request)
            except Exception as exc:  # noqa: BLE001 - qualquer falha de rede/API deve poder ser reciclada
                last_error = str(exc)
                if attempt < attempts:
                    time.sleep(min(2 ** (attempt - 1), 8))

        return AIProviderResponse(success=False, error=last_error)

    def _call(self, request: AIProviderRequest) -> AIProviderResponse:
        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if request.timeout is not None:
            client_kwargs["timeout"] = request.timeout
        client = OpenAI(**client_kwargs)
        response_format: dict[str, str] | None = None
        if request.response_format == "json":
            response_format = {"type": "json_object"}

        model_name = request.model or self.settings.openai_default_model
        create_kwargs: dict[str, Any] = {
            "model": model_name,
            "response_format": response_format,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        # Modelos gpt-5 so aceitam o temperature padrao (1); enviar qualquer
        # outro valor retorna 400 unsupported_value.
        if not model_name.startswith("gpt-5"):
            create_kwargs["temperature"] = request.temperature

        response = client.chat.completions.create(**create_kwargs)
        choice = response.choices[0] if response.choices else None
        content = choice.message.content if choice else None
        finish_reason = choice.finish_reason if choice else None
        usage = response.usage
        raw_response: dict[str, Any] | None = None
        if hasattr(response, "model_dump"):
            raw_response = response.model_dump()
        usage_dict = {
            "input_tokens": usage.prompt_tokens if usage else None,
            "output_tokens": usage.completion_tokens if usage else None,
            "total_tokens": usage.total_tokens if usage else None,
        }

        if finish_reason == "length":
            return AIProviderResponse(
                success=False,
                content=content,
                raw_response=raw_response,
                usage=usage_dict,
                error="Resposta truncada: limite de max_tokens atingido antes da conclusao da geracao.",
                provider_name=self.settings.openai_provider_name,
                model_name=model_name,
                stop_reason=finish_reason,
                truncated=True,
            )

        return AIProviderResponse(
            success=True,
            content=content,
            raw_response=raw_response,
            usage=usage_dict,
            provider_name=self.settings.openai_provider_name,
            model_name=model_name,
            stop_reason=finish_reason,
        )
