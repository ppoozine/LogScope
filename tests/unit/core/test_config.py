from app.core.config import Settings


class TestSettings:
    """Tests for Settings env loading."""

    def test_settings_loads_database_url_from_env(self, monkeypatch):
        """Should load DATABASE_URL from env."""
        # Arrange
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("LOGSCOPE_ADMIN_EMAIL", "a@b.c")
        monkeypatch.setenv("LOGSCOPE_ADMIN_PASSWORD", "x")

        # Act
        settings = Settings()  # type: ignore[call-arg]

        # Assert
        assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/db"
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.session_ttl_seconds == 2592000  # default


def test_copilot_settings_defaults(monkeypatch):
    """Copilot settings should have sensible defaults when env not set."""
    # Arrange: required fields come from .env via SettingsConfigDict; clear
    # only the copilot-specific env so we exercise the in-class defaults.
    for k in [
        "LLM_COPILOT_MODEL",
        "LLM_COPILOT_MAX_HISTORY",
        "LLM_COPILOT_MAX_LOG_LINES_IN_CONTEXT",
        "LLM_COPILOT_MAX_VRL_CHARS_IN_CONTEXT",
    ]:
        monkeypatch.delenv(k, raising=False)

    # Act
    s = Settings()  # type: ignore[call-arg]

    # Assert
    assert s.llm_copilot_model == "claude-haiku-4-5-20251001"
    assert s.llm_copilot_max_history == 20
    assert s.llm_copilot_max_log_lines_in_context == 20
    assert s.llm_copilot_max_vrl_chars_in_context == 4000
