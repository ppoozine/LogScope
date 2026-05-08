import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.library.models.log_type import LogType
from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.library.services.library_overview_service import (
    LibraryOverviewService,
)


def _make_vendor(slug: str = "acme") -> Vendor:
    v = Vendor()
    v.id = uuid.uuid4()
    v.name = "Acme"
    v.slug = slug
    v.logo_url = None
    v.status = "active"
    return v


def _make_product(vendor_id: uuid.UUID, slug: str = "p1") -> Product:
    p = Product()
    p.id = uuid.uuid4()
    p.vendor_id = vendor_id
    p.name = "P1"
    p.slug = slug
    p.status = "active"
    return p


def _make_log_type(product_id: uuid.UUID, status: str = "draft") -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = product_id
    lt.name = "lt"
    lt.slug = "lt"
    lt.status = status
    return lt


def _make_service(*, vendors: list[Vendor], products: dict, log_types: dict):
    """`products` is dict[vendor_id -> list[Product]]; `log_types` is dict[product_id -> list[LogType]]."""
    vendor_repo = MagicMock()
    vendor_repo.list = AsyncMock(return_value=vendors)

    product_repo = MagicMock()
    product_repo.list_by_vendor = AsyncMock(side_effect=lambda vid, *, q=None: products.get(vid, []))

    log_type_repo = MagicMock()
    log_type_repo.list_by_product = AsyncMock(side_effect=lambda pid: log_types.get(pid, []))

    return LibraryOverviewService(vendor_repo, product_repo, log_type_repo)


class TestLibraryOverview:
    """Tests for LibraryOverviewService.overview()."""

    async def test_returns_grouped_with_counts(self):
        """Should return vendor → products with log_type counts."""
        # Arrange
        vendor = _make_vendor()
        product = _make_product(vendor.id)
        log_types = [
            _make_log_type(product.id, "published"),
            _make_log_type(product.id, "published"),
            _make_log_type(product.id, "draft"),
        ]
        service = _make_service(
            vendors=[vendor],
            products={vendor.id: [product]},
            log_types={product.id: log_types},
        )

        # Act
        groups = await service.overview()

        # Assert
        assert len(groups) == 1
        group = groups[0]
        assert group.vendor.slug == "acme"
        assert len(group.products) == 1
        op = group.products[0]
        assert op.log_type_counts.total == 3
        assert op.log_type_counts.published == 2
        assert op.log_type_counts.draft == 1
        assert op.is_empty is False

    async def test_empty_product_marked_is_empty(self):
        """Should set is_empty=True when product has no log types."""
        # Arrange
        vendor = _make_vendor()
        product = _make_product(vendor.id)
        service = _make_service(
            vendors=[vendor],
            products={vendor.id: [product]},
            log_types={},
        )

        # Act
        groups = await service.overview()

        # Assert
        assert groups[0].products[0].is_empty is True
        assert groups[0].products[0].log_type_counts.total == 0


class TestLibraryOverviewQ:
    """Tests for q substring search."""

    async def test_q_filters_by_product_name(self):
        """q should keep products whose name contains the substring."""
        # Arrange
        vendor = _make_vendor()
        p1 = _make_product(vendor.id, "p1")
        p1.name = "Apple"
        # vendor name doesn't match "Apple", so q gets pushed down to product

        vendor_repo = MagicMock()
        vendor_repo.list = AsyncMock(return_value=[vendor])

        product_repo = MagicMock()

        async def list_with_q(vid, *, q=None):
            if q == "Apple":
                return [p1]
            return []

        product_repo.list_by_vendor = AsyncMock(side_effect=list_with_q)

        log_type_repo = MagicMock()
        log_type_repo.list_by_product = AsyncMock(return_value=[])

        service = LibraryOverviewService(vendor_repo, product_repo, log_type_repo)

        # Act
        groups = await service.overview(q="Apple")

        # Assert
        assert len(groups) == 1
        assert len(groups[0].products) == 1
        assert groups[0].products[0].name == "Apple"

    async def test_q_matches_vendor_name_keeps_all_products(self):
        """When vendor.name matches q, all its products are kept regardless."""
        # Arrange
        vendor = _make_vendor()
        vendor.name = "Apple Inc"
        p1 = _make_product(vendor.id, "p1")
        p2 = _make_product(vendor.id, "p2")

        vendor_repo = MagicMock()
        vendor_repo.list = AsyncMock(return_value=[vendor])

        product_repo = MagicMock()

        async def list_with_q(vid, *, q=None):
            assert q is None  # vendor matched, so q should NOT be pushed down
            return [p1, p2]

        product_repo.list_by_vendor = AsyncMock(side_effect=list_with_q)

        log_type_repo = MagicMock()
        log_type_repo.list_by_product = AsyncMock(return_value=[])

        service = LibraryOverviewService(vendor_repo, product_repo, log_type_repo)

        # Act
        groups = await service.overview(q="apple")

        # Assert
        assert len(groups[0].products) == 2
