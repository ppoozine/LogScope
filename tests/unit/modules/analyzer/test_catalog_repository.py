"""Unit tests for CatalogRepository (mocked session)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.analyzer.repositories.catalog_repository import CatalogRepository


class TestCatalogFetchAll:
    """Tests for CatalogRepository.fetch_all()."""

    async def test_returns_rows_with_vendor_product_join(self):
        """Should return rows joining log_type → product → vendor + first sample."""
        # Arrange
        log_type_id = uuid.uuid4()
        base_row = (log_type_id, "palo-alto", "pan-os", "Traffic", "csv")
        sample_row = (log_type_id, "1,2,3")

        base_result = MagicMock()
        base_result.all.return_value = [base_row]

        sample_result = MagicMock()
        sample_result.all.return_value = [sample_row]

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[base_result, sample_result])

        repo = CatalogRepository(mock_session)

        # Act
        rows = await repo.fetch_all()

        # Assert
        assert len(rows) == 1
        assert rows[0].log_type_id == log_type_id
        assert rows[0].vendor_slug == "palo-alto"
        assert rows[0].product_slug == "pan-os"
        assert rows[0].log_type_name == "Traffic"
        assert rows[0].format == "csv"
        assert rows[0].sample == "1,2,3"
