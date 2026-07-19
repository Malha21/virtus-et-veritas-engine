import time
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.core.config import Settings
from app.providers.ai.base import AIProviderRequest, AIProviderResponse

# ServerError cobre 5xx (sobrecarga/erro interno); dentro de ClientError,
# so o 429 (rate limit) e transitorio - os demais (auth, payload invalido,
# modelo inexistente) nao devem consumir tentativas de retry.
def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.ClientError):
        return exc.code == 429
    return False


class GeminiProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_text(self, request: AIProviderRequest) -> AIProviderResponse:
        model_name = request.model or self.settings.gemini_default_model
        if not self.settings.gemini_api_key:
            return self._failure(model_name, "GEMINI_API_KEY nao configurada.")
        if not model_name:
            return self._failure(model_name, "GEMINI_DEFAULT_MODEL nao configurado.")

        attempts = max(request.max_retries, 0) + 1
        last_error: str | None = None

        for attempt in range(1, attempts + 1):
            try:
                return self._call(request, model_name)
            except Exception as exc:  # noqa: BLE001 - reclassificado abaixo por tipo
                if _is_retryable(exc) and attempt < attempts:
                    last_error = self._describe_error(exc)
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
                return self._failure(model_name, self._describe_error(exc))

        return self._failure(model_name, last_error)

    def _failure(self, model_name: str, error: str | None) -> AIProviderResponse:
        return AIProviderResponse(
            success=False,
            error=error,
            provider_name=self.settings.gemini_provider_name,
            model_name=model_name,
        )

    @staticmethod
    def _describe_error(exc: Exception) -> str:
        return f"{type(exc).__name__}: {exc}"

    def _call(self, request: AIProviderRequest, model_name: str) -> AIProviderResponse:
        timeout = request.timeout if request.timeout is not None else self.settings.gemini_timeout_seconds
        http_options = types.HttpOptions(timeout=int(timeout * 1000)) if timeout is not None else None
        client = genai.Client(api_key=self.settings.gemini_api_key, http_options=http_options)

        max_output_tokens = request.max_tokens or self.settings.gemini_max_output_tokens
        config = types.GenerateContentConfig(
            system_instruction=request.system_prompt,
            temperature=request.temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json" if request.response_format == "json" else None,
        )

        response = client.models.generate_content(
            model=model_name,
            contents=request.user_prompt,
            config=config,
        )

        content = response.text
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count if usage else None
        output_tokens = usage.candidates_token_count if usage else None
        total_tokens = usage.total_token_count if usage else None
        raw_response: dict[str, Any] | None = None
        if hasattr(response, "model_dump"):
            raw_response = response.model_dump()

        candidates = response.candidates or []
        finish_reason = candidates[0].finish_reason if candidates else None
        finish_reason_name = getattr(finish_reason, "name", finish_reason)

        if finish_reason_name == "MAX_TOKENS":
            # Geracao truncada: nao deve ser tratada como concluida nem persistida
            # como valida - mesmo contrato de AnthropicProvider/OpenAIProvider.
            return AIProviderResponse(
                success=False,
                content=content or None,
                raw_response=raw_response,
                usage={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                },
                error="Resposta truncada: limite de max_tokens atingido antes da conclusao da geracao.",
                provider_name=self.settings.gemini_provider_name,
                model_name=model_name,
                stop_reason=finish_reason_name,
                truncated=True,
            )

        return AIProviderResponse(
            success=True,
            content=content or None,
            raw_response=raw_response,
            usage={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
            provider_name=self.settings.gemini_provider_name,
            model_name=model_name,
            stop_reason=finish_reason_name,
        )
