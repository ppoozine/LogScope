from app.core.cache import CacheManager


class TestCacheManager:
    """Tests for CacheManager wiring."""

    def test_init_defers_connection(self):
        """Should defer client creation to connect()."""
        # Arrange / Act
        mgr = CacheManager(url="redis://localhost:6379/0")

        # Assert
        assert mgr._client is None
