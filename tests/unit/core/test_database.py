from app.core.database import DatabaseManager


class TestDatabaseManager:
    """Tests for DatabaseManager wiring."""

    def test_init_does_not_connect_immediately(self):
        """Should defer engine creation to connect()."""
        # Arrange / Act
        mgr = DatabaseManager(url="postgresql+asyncpg://u:p@h:5432/db")

        # Assert
        assert mgr._engine is None
        assert mgr._sessionmaker is None
