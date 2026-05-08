import uuid
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import (
    make_mock_session_for_list,
    make_mock_session_for_single,
)

from app.modules.library.models.log_type import LogType
from app.modules.library.repositories.log_type_repository import LogTypeRepository


def _make_log_type(slug: str = "traffic", product_id: uuid.UUID | None = None) -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = product_id or uuid.uuid4()
    lt.name = "Traffic"
    lt.slug = slug
    lt.format = "csv"
    lt.status = "draft"
    lt.source = "manual"
    return lt


class TestLogTypeRepositoryGetByProductAndSlug:
    """Tests for LogTypeRepository.get_by_product_and_slug()."""

    async def test_returns_log_type_when_found(self):
        """Should return LogType when (product_id, slug) matches."""
        # Arrange
        target = _make_log_type()
        session = make_mock_session_for_single(target)
        repo = LogTypeRepository(session)

        # Act
        result = await repo.get_by_product_and_slug(target.product_id, "traffic")

        # Assert
        assert result is target


class TestLogTypeRepositoryListByProduct:
    """Tests for LogTypeRepository.list_by_product()."""

    async def test_returns_log_types_for_product(self):
        """Should return scoped list."""
        # Arrange
        product_id = uuid.uuid4()
        log_types = [_make_log_type("a", product_id), _make_log_type("b", product_id)]
        session = make_mock_session_for_list(log_types)
        repo = LogTypeRepository(session)

        # Act
        result = await repo.list_by_product(product_id)

        # Assert
        assert result == log_types


class TestLogTypeRepositoryCreate:
    """Tests for LogTypeRepository.create()."""

    async def test_creates_and_returns(self):
        """Should add, flush, refresh, return."""
        # Arrange
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = LogTypeRepository(session)
        log_type = _make_log_type()

        # Act
        result = await repo.create(log_type)

        # Assert
        assert result is log_type
