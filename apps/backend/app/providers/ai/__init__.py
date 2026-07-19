from app.core.config import Settings
from app.providers.ai.anthropic_provider import AnthropicProvider
from app.providers.ai.base import AIProvider, AIProviderRequest, AIProviderResponse
from app.providers.ai.gemini_provider import GeminiProvider
from app.providers.ai.openai_provider import OpenAIProvider

__all__ = [
    "AIProvider",
    "AIProviderRequest",
    "AIProviderResponse",
    "AnthropicProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "get_ai_provider",
    "resolve_provider_key",
    "resolve_provider_name",
    "resolve_default_model",
    "resolve_api_key",
]

PROVIDER_KEYS = ("openai", "anthropic", "gemini")


def resolve_provider_key(settings: Settings, requested: str | None) -> str:
    """Resolve o provedor a usar: o pedido explicitamente (ex.: project.ai_provider),
    se for um dos suportados, ou o padrao do sistema (settings.ai_provider) caso
    contrario (projeto sem escolha, ou valor desconhecido/legado).
    """
    if requested in PROVIDER_KEYS:
        return requested
    return settings.ai_provider


def resolve_provider_name(settings: Settings, provider_key: str) -> str:
    if provider_key == "openai":
        return settings.openai_provider_name
    if provider_key == "gemini":
        return settings.gemini_provider_name
    return settings.anthropic_provider_name


def resolve_default_model(settings: Settings, provider_key: str) -> str:
    if provider_key == "openai":
        return settings.openai_default_model
    if provider_key == "gemini":
        return settings.gemini_default_model
    return settings.anthropic_default_model


def resolve_api_key(settings: Settings, provider_key: str) -> str:
    if provider_key == "openai":
        return settings.openai_api_key
    if provider_key == "gemini":
        return settings.gemini_api_key
    return settings.anthropic_api_key


def get_ai_provider(settings: Settings, provider: str | None = None) -> AIProvider:
    """Retorna a implementacao de AIProvider para o provedor pedido (ex.: o
    ai_provider escolhido no projeto), caindo para o padrao do sistema
    (settings.ai_provider) quando nao especificado ou desconhecido.
    """
    key = resolve_provider_key(settings, provider)
    if key == "openai":
        return OpenAIProvider(settings)
    if key == "gemini":
        return GeminiProvider(settings)
    return AnthropicProvider(settings)
