from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Virtus et Veritas Engine", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    database_url: str = Field(
        default="postgresql+psycopg://vve_user:change_me_secure_password@postgres:5432/vve_engine",
        alias="DATABASE_URL",
    )
    jwt_secret: str = Field(default="change_me_super_secret_key", alias="JWT_SECRET")
    jwt_expires_minutes: int = Field(default=1440, alias="JWT_EXPIRES_MINUTES")
    seed_organization_name: str = Field(
        default="Virtus et Veritas Academy",
        alias="SEED_ORGANIZATION_NAME",
    )
    seed_organization_slug: str = Field(
        default="virtus-et-veritas-academy",
        alias="SEED_ORGANIZATION_SLUG",
    )
    seed_admin_name: str = Field(default="Leonardo Elias", alias="SEED_ADMIN_NAME")
    seed_admin_email: str = Field(default="admin@example.com", alias="SEED_ADMIN_EMAIL")
    seed_admin_password: str = Field(
        default="change_me_admin_password",
        alias="SEED_ADMIN_PASSWORD",
    )
    openai_provider_name: str = Field(default="OpenAI", alias="OPENAI_PROVIDER_NAME")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_default_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_DEFAULT_MODEL")
    openai_tts_model: str = Field(default="gpt-4o-mini-tts", alias="OPENAI_TTS_MODEL")
    openai_tts_voice: str = Field(default="alloy", alias="OPENAI_TTS_VOICE")
    openai_tts_format: str = Field(default="mp3", alias="OPENAI_TTS_FORMAT")
    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    elevenlabs_tts_model: str = Field(default="eleven_multilingual_v2", alias="ELEVENLABS_TTS_MODEL")
    elevenlabs_output_format: str = Field(default="mp3_44100_128", alias="ELEVENLABS_OUTPUT_FORMAT")
    storage_driver: str = Field(default="local", alias="STORAGE_DRIVER")
    storage_path: str = Field(default="/app/storage", alias="STORAGE_PATH")
    max_upload_size_mb: int = Field(default=100, alias="MAX_UPLOAD_SIZE_MB")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
