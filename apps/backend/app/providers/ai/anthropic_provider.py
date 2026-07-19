import time
from typing import Any

import anthropic
from anthropic import Anthropic

from app.core.config import Settings
from app.providers.ai.base import AIProviderRequest, AIProviderResponse

# Erros transitorios (rede, rate limit, sobrecarga, erro interno) podem ser
# reenviados; erros permanentes (auth, payload invalido, modelo inexistente)
# nao devem consumir tentativas de retry.
_RETRYABLE_EXCEPTIONS = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)


class AnthropicProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_text(self, request: AIProviderRequest) -> AIProviderResponse:
        model_name = request.model or self.settings.anthropic_default_model
        if not self.settings.anthropic_api_key:
            return self._failure(model_name, "ANTHROPIC_API_KEY nao configurada.")
        if not model_name:
            return self._failure(model_name, "ANTHROPIC_MODEL nao configurado.")

        attempts = max(request.max_retries, 0) + 1
        last_error: str | None = None

        for attempt in range(1, attempts + 1):
            try:
                return self._call(request, model_name)
            except (*_RETRYABLE_EXCEPTIONS,) as exc:
                last_error = self._describe_error(exc)
            except anthropic.APIStatusError as exc:
                if exc.status_code == 529:  # overloaded_error - transitorio
                    last_error = self._describe_error(exc)
                else:
                    return self._failure(model_name, self._describe_error(exc))
            except anthropic.APIError as exc:
                return self._failure(model_name, self._describe_error(exc))

            if attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 8))

        return self._failure(model_name, last_error)

    def _failure(self, model_name: str, error: str | None) -> AIProviderResponse:
        return AIProviderResponse(
            success=False,
            error=error,
            provider_name=self.settings.anthropic_provider_name,
            model_name=model_name,
        )

    @staticmethod
    def _describe_error(exc: Exception) -> str:
        return f"{type(exc).__name__}: {exc}"

    def _call(self, request: AIProviderRequest, model_name: str) -> AIProviderResponse:
        client_kwargs: dict[str, Any] = {"api_key": self.settings.anthropic_api_key}
        timeout = request.timeout if request.timeout is not None else self.settings.anthropic_timeout_seconds
        if timeout is not None:
            client_kwargs["timeout"] = timeout
        if self.settings.anthropic_base_url:
            client_kwargs["base_url"] = self.settings.anthropic_base_url
        client = Anthropic(**client_kwargs)

        max_tokens = request.max_tokens or self.settings.anthropic_max_tokens

        response = client.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            temperature=request.temperature,
            system=request.system_prompt,
            messages=[{"role": "user", "content": request.user_prompt}],
        )

        content = "".join(block.text for block in response.content if block.type == "text")
        usage = response.usage
        input_tokens = usage.input_tokens if usage else None
        output_tokens = usage.output_tokens if usage else None
        total_tokens = (
            input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None
        )
        raw_response = response.model_dump() if hasattr(response, "model_dump") else None
        stop_reason = response.stop_reason

        if stop_reason == "max_tokens":
            # Geracao truncada: nao deve ser tratada como concluida nem persistida
            # como valida - ver secao 14/15 da especificacao de migracao.
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
                provider_name=self.settings.anthropic_provider_name,
                model_name=model_name,
                stop_reason=stop_reason,
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
            provider_name=self.settings.anthropic_provider_name,
            model_name=model_name,
            stop_reason=stop_reason,
        )
