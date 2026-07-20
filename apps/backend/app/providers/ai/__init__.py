from app.core.config import Settings
from app.providers.ai.base import AIProvider, AIProviderRequest, AIProviderResponse
from app.providers.ai.gemini_provider import GeminiProvider
from app.providers.ai.openai_provider import OpenAIProvider

__all__ = [
    "AIProvider",
    "AIProviderRequest",
    "AIProviderResponse",
    "GeminiProvider",
    "OpenAIProvider",
    "get_ai_provider",
    "resolve_provider_key",
    "resolve_provider_name",
    "resolve_default_model",
    "resolve_api_key",
]

PROVIDER_KEYS = ("openai", "gemini")


def resolve_provider_key(settings: Settings, requested: str | None) -> str:
    """Resolve o provedor a usar: o pedido explicitamente (ex.: project.ai_provider),
    se for um dos suportados, ou o padrao do sistema (settings.ai_provider) caso
    contrario (projeto sem escolha, ou valor desconhecido/legado - ex.: "anthropic",
    removido do sistema).
    """
    if requested in PROVIDER_KEYS:
        return requested
    return settings.ai_provider


def resolve_provider_name(settings: Settings, provider_key: str) -> str:
    if provider_key == "gemini":
        return settings.gemini_provider_name
    return settings.openai_provider_name


def resolve_default_model(settings: Settings, provider_key: str) -> str:
    if provider_key == "gemini":
        return settings.gemini_default_model
    return settings.openai_default_model


def resolve_api_key(settings: Settings, provider_key: str) -> str:
    if provider_key == "gemini":
        return settings.gemini_api_key
    return settings.openai_api_key


def get_ai_provider(
    settings: Settings,
    provider: str | None = None,
    api_key_override: str | None = None,
    base_url_override: str | None = None,
) -> AIProvider:
    """Retorna a implementacao de AIProvider para o provedor pedido (ex.: o
    ai_provider escolhido no projeto), caindo para o padrao do sistema
    (settings.ai_provider) quando nao especificado ou desconhecido.

    api_key_override, quando informado, e a chave pessoal do usuario para o
    provedor (cadastrada em /account/api-keys) e tem prioridade sobre a chave
    global do .env. base_url_override, quando informado, substitui o host
    padrao do provedor (ex.: proxy, gateway proprio, Azure OpenAI).
    """
    key = resolve_provider_key(settings, provider)
    if key == "gemini":
        return GeminiProvider(settings, api_key=api_key_override, base_url=base_url_override)
    return OpenAIProvider(settings, api_key=api_key_override, base_url=base_url_override)
