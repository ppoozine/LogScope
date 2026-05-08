import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.library.models.product import Product
from app.modules.library.repositories.product_repository import ProductRepository
from tests.conftest import (
    make_mock_session_for_list,
    make_mock_session_for_single,
)


def _make_product(slug: str = "pan-os", vendor_id: uuid.UUID | None = None) -> Product:
    p = Product()
    p.id = uuid.uuid4()
    p.vendor_id = vendor_id or uuid.uuid4()
    p.name = "PAN-OS"
    p.slug = slug
    p.status = "active"
    return p


class TestProductRepositoryGetByVendorAndSlug:
    """Tests for ProductRepository.get_by_vendor_and_slug()."""

    async def test_returns_product_when_found(self):
        """Should return Product when (vendor_id, slug) matches."""
        # Arrange
        target = _make_product()
        session = make_mock_session_for_single(target)
        repo = ProductRepository(session)

        # Act
        result = await repo.get_by_vendor_and_slug(target.vendor_id, "pan-os")

        # Assert
        assert result is target


class TestProductRepositoryListByVendor:
    """Tests for ProductRepository.list_by_vendor()."""

    async def test_returns_products_for_vendor(self):
        """Should return products belonging to the vendor."""
        # Arrange
        vendor_id = uuid.uuid4()
        products = [_make_product("a", vendor_id), _make_product("b", vendor_id)]
        session = make_mock_session_for_list(products)
        repo = ProductRepository(session)

        # Act
        result = await repo.list_by_vendor(vendor_id)

        # Assert
        assert result == products


    async def test_list_by_vendor_filters_by_q(self):
        """list_by_vendor(q='pan') should only return products whose name matches."""
        # Arrange
        vendor_id = uuid.uuid4()
        p1 = _make_product("pan-os", vendor_id)
        session = make_mock_session_for_list([p1])
        repo = ProductRepository(session)

        # Act
        result = await repo.list_by_vendor(vendor_id, q="pan")

        # Assert
        assert result == [p1]


class TestProductRepositoryCreate:
    """Tests for ProductRepository.create()."""

    async def test_creates_and_flushes(self):
        """Should add, flush, refresh, and return."""
        # Arrange
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = ProductRepository(session)
        product = _make_product()

        # Act
        result = await repo.create(product)

        # Assert
        session.add.assert_called_once_with(product)
        session.flush.assert_awaited_once()
        assert result is product
