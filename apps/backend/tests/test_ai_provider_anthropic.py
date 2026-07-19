"""Testes da camada de provider de IA (migracao OpenAI -> Anthropic).

Cobre a abstracao AIProvider, o AnthropicProvider (novo provider padrao) e a
factory get_ai_provider. Nao realiza nenhuma chamada de rede real: o cliente
anthropic.Anthropic e substituido por um dublê determinístico via monkeypatch.
"""

from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.core.config import Settings
from app.providers.ai import AnthropicProvider, OpenAIProvider, get_ai_provider
from app.providers.ai import anthropic_provider as anthropic_provider_module
from app.providers.ai.base import AIProviderRequest


def make_settings(**overrides) -> Settings:
    # Settings usa Field(alias="ANTHROPIC_...") sem populate_by_name=True, entao
    # o construtor so aceita os aliases em maiusculas (mesmo nome das env vars).
    defaults = dict(
        AI_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="sk-ant-test-key",
        ANTHROPIC_MODEL="claude-opus-4-8",
        ANTHROPIC_MAX_TOKENS=1024,
        ANTHROPIC_TIMEOUT_SECONDS=30.0,
        ANTHROPIC_PROVIDER_NAME="Anthropic",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def fake_message(text: str, *, stop_reason: str = "end_turn", input_tokens: int = 50, output_tokens: int = 20):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason=stop_reason,
    )


def install_fake_client(monkeypatch, queue: list, client_inits: list | None = None):
    """Substitui anthropic.Anthropic por um dublê cujo messages.create() consome
    `queue` em ordem (itens Exception sao levantados; os demais sao retornados
    como se fossem a resposta do SDK). Retorna a lista de kwargs de cada chamada
    a messages.create(); se `client_inits` for passado, tambem acumula os kwargs
    usados para instanciar o client (ex.: para inspecionar `timeout`)."""
    calls: list[dict] = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if not queue:
                raise AssertionError("fake client chamado mais vezes do que o esperado")
            item = queue.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

    class FakeAnthropic:
        def __init__(self, **kwargs):
            self.init_kwargs = kwargs
            if client_inits is not None:
                client_inits.append(kwargs)
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    return calls


def http_error(exc_cls, status_code: int, message: str = "erro"):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request, json={"error": {"message": message}})
    return exc_cls(message, response=response, body=None)


# --------------------------------------------------------------------------
# Chamada basica: system prompt / user message / texto de resposta
# --------------------------------------------------------------------------

def test_generate_text_sends_system_param_and_user_message(monkeypatch):
    settings = make_settings()
    calls = install_fake_client(monkeypatch, [fake_message('{"ok": true}')])

    provider = AnthropicProvider(settings)
    response = provider.generate_text(
        AIProviderRequest(system_prompt="Voce e um assistente.", user_prompt="Gere um JSON.")
    )

    assert response.success is True
    assert response.content == '{"ok": true}'
    assert len(calls) == 1
    assert calls[0]["system"] == "Voce e um assistente."
    assert calls[0]["messages"] == [{"role": "user", "content": "Gere um JSON."}]
    assert calls[0]["model"] == "claude-opus-4-8"


def test_generate_text_uses_request_model_override(monkeypatch):
    settings = make_settings()
    calls = install_fake_client(monkeypatch, [fake_message("ok")])

    provider = AnthropicProvider(settings)
    provider.generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u", model="claude-sonnet-5")
    )

    assert calls[0]["model"] == "claude-sonnet-5"


def test_max_tokens_defaults_from_settings_when_not_in_request(monkeypatch):
    settings = make_settings(ANTHROPIC_MAX_TOKENS=4096)
    calls = install_fake_client(monkeypatch, [fake_message("ok")])

    AnthropicProvider(settings).generate_text(AIProviderRequest(system_prompt="s", user_prompt="u"))

    assert calls[0]["max_tokens"] == 4096


def test_max_tokens_request_override_wins(monkeypatch):
    settings = make_settings(ANTHROPIC_MAX_TOKENS=4096)
    calls = install_fake_client(monkeypatch, [fake_message("ok")])

    AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u", max_tokens=16000)
    )

    assert calls[0]["max_tokens"] == 16000


def test_timeout_defaults_from_settings_when_not_in_request(monkeypatch):
    settings = make_settings(ANTHROPIC_TIMEOUT_SECONDS=42.0)
    client_inits: list[dict] = []
    install_fake_client(monkeypatch, [fake_message("ok")], client_inits)

    AnthropicProvider(settings).generate_text(AIProviderRequest(system_prompt="s", user_prompt="u"))

    assert client_inits[0]["timeout"] == 42.0


def test_timeout_request_override_wins(monkeypatch):
    settings = make_settings(ANTHROPIC_TIMEOUT_SECONDS=42.0)
    client_inits: list[dict] = []
    install_fake_client(monkeypatch, [fake_message("ok")], client_inits)

    AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u", timeout=7.5)
    )

    assert client_inits[0]["timeout"] == 7.5


# --------------------------------------------------------------------------
# Configuracao ausente
# --------------------------------------------------------------------------

def test_missing_api_key_fails_without_network_call(monkeypatch):
    settings = make_settings(ANTHROPIC_API_KEY="")
    calls = install_fake_client(monkeypatch, [])

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u")
    )

    assert response.success is False
    assert "ANTHROPIC_API_KEY" in response.error
    assert calls == []


def test_missing_model_fails_without_network_call(monkeypatch):
    settings = make_settings(ANTHROPIC_MODEL="")
    calls = install_fake_client(monkeypatch, [])

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u")
    )

    assert response.success is False
    assert "ANTHROPIC_MODEL" in response.error
    assert calls == []


# --------------------------------------------------------------------------
# Truncamento (stop_reason == max_tokens)
# --------------------------------------------------------------------------

def test_truncated_response_is_marked_as_failure(monkeypatch):
    settings = make_settings()
    install_fake_client(monkeypatch, [fake_message("resposta incompleta...", stop_reason="max_tokens")])

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u")
    )

    assert response.success is False
    assert response.truncated is True
    assert response.stop_reason == "max_tokens"
    assert "truncada" in response.error.lower()
    # o conteudo parcial fica disponivel para diagnostico, mas nao deve ser
    # tratado como geracao valida por quem chama.
    assert response.content == "resposta incompleta..."


def test_normal_completion_is_not_marked_truncated(monkeypatch):
    settings = make_settings()
    install_fake_client(monkeypatch, [fake_message("ok", stop_reason="end_turn")])

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u")
    )

    assert response.success is True
    assert response.truncated is False
    assert response.stop_reason == "end_turn"


# --------------------------------------------------------------------------
# Retries: transitorios vs permanentes
# --------------------------------------------------------------------------

def test_retries_on_rate_limit_then_succeeds(monkeypatch):
    settings = make_settings()
    monkeypatch.setattr(anthropic_provider_module.time, "sleep", lambda _seconds: None)
    calls = install_fake_client(
        monkeypatch,
        [http_error(anthropic.RateLimitError, 429), fake_message("ok")],
    )

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u", max_retries=2)
    )

    assert response.success is True
    assert len(calls) == 2


def test_retries_on_overloaded_529_then_succeeds(monkeypatch):
    settings = make_settings()
    monkeypatch.setattr(anthropic_provider_module.time, "sleep", lambda _seconds: None)
    calls = install_fake_client(
        monkeypatch,
        [http_error(anthropic.APIStatusError, 529), fake_message("ok")],
    )

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u", max_retries=2)
    )

    assert response.success is True
    assert len(calls) == 2


def test_retries_on_connection_error_then_succeeds(monkeypatch):
    settings = make_settings()
    monkeypatch.setattr(anthropic_provider_module.time, "sleep", lambda _seconds: None)
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    calls = install_fake_client(
        monkeypatch,
        [anthropic.APIConnectionError(request=request), fake_message("ok")],
    )

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u", max_retries=2)
    )

    assert response.success is True
    assert len(calls) == 2


def test_retry_exhaustion_returns_last_error(monkeypatch):
    settings = make_settings()
    monkeypatch.setattr(anthropic_provider_module.time, "sleep", lambda _seconds: None)
    calls = install_fake_client(
        monkeypatch,
        [
            http_error(anthropic.RateLimitError, 429, "limite 1"),
            http_error(anthropic.RateLimitError, 429, "limite 2"),
            http_error(anthropic.RateLimitError, 429, "limite final"),
        ],
    )

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u", max_retries=2)
    )

    assert response.success is False
    assert "limite final" in response.error
    assert len(calls) == 3


@pytest.mark.parametrize(
    "exc_factory",
    [
        lambda: http_error(anthropic.AuthenticationError, 401, "chave invalida"),
        lambda: http_error(anthropic.PermissionDeniedError, 403, "sem permissao"),
        lambda: http_error(anthropic.NotFoundError, 404, "modelo inexistente"),
        lambda: http_error(anthropic.BadRequestError, 400, "payload invalido"),
    ],
)
def test_permanent_errors_are_not_retried(monkeypatch, exc_factory):
    settings = make_settings()
    monkeypatch.setattr(anthropic_provider_module.time, "sleep", lambda _seconds: None)
    calls = install_fake_client(monkeypatch, [exc_factory()])

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u", max_retries=3)
    )

    assert response.success is False
    # Erros permanentes nao devem consumir tentativas de retry: apenas 1 chamada.
    assert len(calls) == 1


# --------------------------------------------------------------------------
# Tokens / metadados registrados
# --------------------------------------------------------------------------

def test_usage_tokens_are_mapped(monkeypatch):
    settings = make_settings()
    install_fake_client(monkeypatch, [fake_message("ok", input_tokens=123, output_tokens=45)])

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u")
    )

    assert response.usage["input_tokens"] == 123
    assert response.usage["output_tokens"] == 45
    assert response.usage["total_tokens"] == 168


def test_provider_name_and_model_name_recorded_on_success(monkeypatch):
    settings = make_settings(ANTHROPIC_PROVIDER_NAME="Anthropic")
    install_fake_client(monkeypatch, [fake_message("ok")])

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u")
    )

    assert response.provider_name == "Anthropic"
    assert response.model_name == "claude-opus-4-8"


def test_provider_name_and_model_name_recorded_on_failure(monkeypatch):
    settings = make_settings()
    install_fake_client(monkeypatch, [http_error(anthropic.BadRequestError, 400)])

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u")
    )

    assert response.provider_name == "Anthropic"
    assert response.model_name == "claude-opus-4-8"


# --------------------------------------------------------------------------
# Factory get_ai_provider e integracao com validacao Pydantic downstream
# --------------------------------------------------------------------------

def test_factory_returns_anthropic_provider_by_default():
    settings = make_settings(AI_PROVIDER="anthropic")
    assert isinstance(get_ai_provider(settings), AnthropicProvider)


def test_factory_returns_openai_provider_when_configured():
    settings = make_settings(AI_PROVIDER="openai")
    assert isinstance(get_ai_provider(settings), OpenAIProvider)


def test_json_content_is_passed_through_untouched_for_downstream_pydantic_validation(monkeypatch):
    """O provider nao faz parsing/validacao de JSON: apenas repassa o texto cru.
    A extracao (parse_json_content) e a validacao Pydantic continuam
    responsabilidade das camadas de servico, preservadas pela migracao."""
    from app.services.ai_orchestrator_service import parse_json_content

    settings = make_settings()
    install_fake_client(monkeypatch, [fake_message('```json\n{"course": {"title": "X"}}\n```')])

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u")
    )

    parsed = parse_json_content(response.content)
    assert parsed == {"course": {"title": "X"}}


def test_invalid_json_content_raises_in_parse_json_content(monkeypatch):
    from app.services.ai_orchestrator_service import parse_json_content

    settings = make_settings()
    install_fake_client(monkeypatch, [fake_message("isso nao e json valido")])

    response = AnthropicProvider(settings).generate_text(
        AIProviderRequest(system_prompt="s", user_prompt="u")
    )

    with pytest.raises(Exception):
        parse_json_content(response.content)
