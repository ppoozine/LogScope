from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    # Cookie name 固定為 "session"，不暴露為 setting（避免 dep alias 與 settings 失聯）
    session_cookie_secure: bool = Field(False, alias="SESSION_COOKIE_SECURE")
    session_ttl_seconds: int = Field(2592000, alias="SESSION_TTL_SECONDS")

    admin_email: str = Field(..., alias="LOGSCOPE_ADMIN_EMAIL")
    admin_password: str = Field(..., alias="LOGSCOPE_ADMIN_PASSWORD")

    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    llm_match_model: str = Field("claude-haiku-4-5-20251001", alias="LLM_MATCH_MODEL")

    clickhouse_url: str | None = Field(default=None, alias="CLICKHOUSE_URL")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
