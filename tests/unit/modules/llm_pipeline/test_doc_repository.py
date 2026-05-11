import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.modules.llm_pipeline.models import Doc
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository


def _make_doc() -> Doc:
    doc = Doc()
    doc.id = uuid.uuid4()
    doc.vendor_id = uuid.uuid4()
    doc.url = "https://example.com/doc"
    doc.title = "Example"
    doc.content = "# heading\n"
    doc.content_format = "markdown"
    doc.fetched_at = datetime.now(UTC)
    doc.fetched_by = "manual"
    return doc


class TestDocRepositoryCreate:
    """Tests for DocRepository.create()."""

    async def test_create_calls_add_flush_refresh(self):
        """Should add, flush, refresh, return the doc."""
        # Arrange
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = DocRepository(session)
        doc = _make_doc()

        # Act
        result = await repo.create(doc)

        # Assert
        session.add.assert_called_once_with(doc)
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(doc)
        assert result is doc


class TestDocRepositoryGetById:
    """Tests for DocRepository.get_by_id()."""

    async def test_get_by_id_returns_doc(self):
        """Should call session.get(Doc, doc_id) and return the result."""
        # Arrange
        target = _make_doc()
        session = MagicMock()
        session.get = AsyncMock(return_value=target)
        repo = DocRepository(session)

        # Act
        result = await repo.get_by_id(target.id)

        # Assert
        session.get.assert_awaited_once_with(Doc, target.id)
        assert result is target
