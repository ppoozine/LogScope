import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.library.models.vendor import Vendor
from app.modules.library.repositories.vendor_repository import VendorRepository
from tests.conftest import (
    make_mock_session_for_list,
    make_mock_session_for_single,
)


def _make_vendor(slug: str = "acme", name: str = "Acme") -> Vendor:
    v = Vendor()
    v.id = uuid.uuid4()
    v.name = name
    v.slug = slug
    v.status = "active"
    return v


class TestVendorRepositoryGetBySlug:
    """Tests for VendorRepository.get_by_slug()."""

    async def test_returns_vendor_when_found(self):
        """Should return Vendor when slug matches."""
        # Arrange
        target = _make_vendor("acme")
        session = make_mock_session_for_single(target)
        repo = VendorRepository(session)

        # Act
        result = await repo.get_by_slug("acme")

        # Assert
        assert result is target
        session.execute.assert_awaited_once()

    async def test_returns_none_when_missing(self):
        """Should return None when slug does not exist."""
        # Arrange
        session = make_mock_session_for_single(None)
        repo = VendorRepository(session)

        # Act
        result = await repo.get_by_slug("missing")

        # Assert
        assert result is None


class TestVendorRepositoryList:
    """Tests for VendorRepository.list()."""

    async def test_returns_all_vendors(self):
        """Should return list of vendors from session."""
        # Arrange
        vendors = [_make_vendor("a"), _make_vendor("b")]
        session = make_mock_session_for_list(vendors)
        repo = VendorRepository(session)

        # Act
        result = await repo.list()

        # Assert
        assert result == vendors

    async def test_list_filters_by_q(self):
        """list(q='apple') should only return vendors whose name matches."""
        # Arrange
        apple = _make_vendor("apple", "Apple Inc")
        # Mock session 只回 apple（DB 端已過濾）
        session = make_mock_session_for_list([apple])
        repo = VendorRepository(session)

        # Act
        result = await repo.list(q="apple")

        # Assert
        assert result == [apple]
        session.execute.assert_awaited_once()


class TestVendorRepositoryCreate:
    """Tests for VendorRepository.create()."""

    async def test_creates_and_flushes(self):
        """Should add Vendor to session, flush, refresh, and return it."""
        # Arrange
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = VendorRepository(session)
        vendor = _make_vendor()

        # Act
        result = await repo.create(vendor)

        # Assert
        session.add.assert_called_once_with(vendor)
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(vendor)
        assert result is vendor


class TestVendorRepositoryDelete:
    """Tests for VendorRepository.delete()."""

    async def test_deletes_vendor(self):
        """Should call session.delete and flush."""
        # Arrange
        session = MagicMock()
        session.delete = AsyncMock()
        session.flush = AsyncMock()
        repo = VendorRepository(session)
        vendor = _make_vendor()

        # Act
        await repo.delete(vendor)

        # Assert
        session.delete.assert_awaited_once_with(vendor)
        session.flush.assert_awaited_once()
