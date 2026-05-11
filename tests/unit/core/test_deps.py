"""Tests for shared dependency providers."""
from app.core.deps import get_anthropic_client


class TestGetAnthropicClient:
    def test_returns_async_anthropic_instance(self):
        """Returns an object that quacks like AsyncAnthropic (has .messages)."""
        client = get_anthropic_client()
        assert client is not None
        assert hasattr(client, "messages")

    def test_singleton_returns_same_instance(self):
        """lru_cache should make repeated calls return the same instance."""
        c1 = get_anthropic_client()
        c2 = get_anthropic_client()
        assert c1 is c2

    def test_uses_settings_api_key(self, monkeypatch):
        """Client should pick up ANTHROPIC_API_KEY from settings.

        ``get_settings`` uses a module-level cache (not lru_cache), so we reset
        ``_settings`` directly. We also clear the deps lru_cache so the new
        settings actually flow through to a fresh client.
        """
        from app.core import config as config_module

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-xyz")
        # Required fields still need values (Settings reads .env by default,
        # but we make this independent of local .env).
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql+asyncpg://t:t@localhost:5432/t"
        )
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("LOGSCOPE_ADMIN_EMAIL", "a@b.c")
        monkeypatch.setenv("LOGSCOPE_ADMIN_PASSWORD", "x")

        monkeypatch.setattr(config_module, "_settings", None)
        get_anthropic_client.cache_clear()  # type: ignore[attr-defined]
        try:
            client = get_anthropic_client()
            assert client.api_key == "test-key-xyz"
        finally:
            monkeypatch.setattr(config_module, "_settings", None)
            get_anthropic_client.cache_clear()  # type: ignore[attr-defined]
