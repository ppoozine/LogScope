import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from tests.conftest import make_mock_session_for_list, make_mock_session_for_single


def _make_parse_rule(version: int = 1, log_type_id: uuid.UUID | None = None) -> ParseRule:
    pr = ParseRule()
    pr.id = uuid.uuid4()
    pr.log_type_id = log_type_id or uuid.uuid4()
    pr.version = version
    pr.vrl_code = ".action = 'allow'"
    pr.engine_version = "0.32"
    pr.status = "draft"
    return pr


class TestParseRuleRepositoryListByLogType:
    """Tests for ParseRuleRepository.list_by_log_type()."""

    async def test_returns_versions_descending(self):
        """Should return all parse rules for log type."""
        # Arrange
        log_type_id = uuid.uuid4()
        rules = [
            _make_parse_rule(2, log_type_id),
            _make_parse_rule(1, log_type_id),
        ]
        session = make_mock_session_for_list(rules)
        repo = ParseRuleRepository(session)

        # Act
        result = await repo.list_by_log_type(log_type_id)

        # Assert
        assert result == rules


class TestParseRuleRepositoryGetMaxVersion:
    """Tests for ParseRuleRepository.get_max_version()."""

    async def test_returns_max_version_when_rules_exist(self):
        """Should return the max version int."""
        # Arrange
        session = make_mock_session_for_single(3)
        repo = ParseRuleRepository(session)

        # Act
        result = await repo.get_max_version(uuid.uuid4())

        # Assert
        assert result == 3

    async def test_returns_zero_when_no_rules(self):
        """Should return 0 when no rows."""
        # Arrange
        session = make_mock_session_for_single(None)
        repo = ParseRuleRepository(session)

        # Act
        result = await repo.get_max_version(uuid.uuid4())

        # Assert
        assert result == 0


class TestParseRuleRepositoryCreate:
    """Tests for ParseRuleRepository.create()."""

    async def test_creates_and_returns(self):
        """Should add, flush, refresh."""
        # Arrange
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = ParseRuleRepository(session)
        rule = _make_parse_rule()

        # Act
        result = await repo.create(rule)

        # Assert
        assert result is rule
