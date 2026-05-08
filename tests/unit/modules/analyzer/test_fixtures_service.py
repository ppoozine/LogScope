"""Unit tests for fixtures_service."""

from app.modules.analyzer.services import fixtures_service


class TestListFixtures:
    """Tests for fixtures_service.list_fixtures()."""

    def test_loads_bundled_fixtures(self):
        """Should find at least the 3 bundled fixtures."""
        # Arrange / Act
        items = fixtures_service.list_fixtures()
        ids = {f.id for f in items}

        # Assert — sanity check the bundled ones exist
        assert "keycloak" in ids
        assert "simple-json" in ids
        assert "simple-syslog" in ids

    def test_fixture_shape(self):
        """Each fixture exposes id/name/description/vrl/logs/engine."""
        # Arrange
        items = fixtures_service.list_fixtures()
        item = next(f for f in items if f.id == "simple-json")

        # Assert
        assert item.name
        assert item.vrl  # parser.vrl content
        assert item.logs  # logs.txt content
        assert item.engine_version in ("0.25", "0.32")
