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
        settings = Settings()

        # Assert
        assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/db"
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.session_ttl_seconds == 2592000  # default
