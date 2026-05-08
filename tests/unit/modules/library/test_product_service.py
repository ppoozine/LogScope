import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.library.schemas import ProductCreate, ProductUpdate
from app.modules.library.services.product_service import ProductService


def _make_vendor() -> Vendor:
    v = Vendor()
    v.id = uuid.uuid4()
    v.slug = "acme"
    return v


def _make_product(vendor_id: uuid.UUID, slug: str = "pan-os") -> Product:
    p = Product()
    p.id = uuid.uuid4()
    p.vendor_id = vendor_id
    p.name = "PAN-OS"
    p.slug = slug
    p.status = "active"
    return p


def _make_service(
    *,
    vendor_get_by_slug: Vendor | None = None,
    product_get_by_vendor_slug: Product | None = None,
    product_get_by_id: Product | None = None,
):
    vendor_repo = MagicMock()
    vendor_repo.get_by_slug = AsyncMock(return_value=vendor_get_by_slug)

    product_repo = MagicMock()
    product_repo.get_by_vendor_and_slug = AsyncMock(return_value=product_get_by_vendor_slug)
    product_repo.get_by_id = AsyncMock(return_value=product_get_by_id)
    product_repo.list_by_vendor = AsyncMock(return_value=[])
    product_repo.create = AsyncMock(side_effect=lambda p: p)
    product_repo.update = AsyncMock(side_effect=lambda p: p)
    product_repo.delete = AsyncMock(return_value=None)

    return ProductService(product_repo, vendor_repo), product_repo, vendor_repo


class TestProductServiceCreate:
    """Tests for ProductService.create()."""

    async def test_create_under_vendor_slug(self):
        """Should create product under a vendor identified by slug."""
        # Arrange
        vendor = _make_vendor()
        service, _product_repo, _ = _make_service(vendor_get_by_slug=vendor)
        request = ProductCreate(name="PAN-OS")

        # Act
        result = await service.create(vendor.slug, request, current_user_id=uuid.uuid4())

        # Assert
        assert result.vendor_id == vendor.id
        assert result.slug == "pan-os"

    async def test_create_raises_when_vendor_missing(self):
        """Should raise NotFoundError when vendor slug invalid."""
        # Arrange
        service, _, _ = _make_service(vendor_get_by_slug=None)
        request = ProductCreate(name="PAN-OS")

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.create("missing", request, current_user_id=uuid.uuid4())

    async def test_create_raises_conflict_when_slug_used_in_vendor(self):
        """Should raise ConflictError if (vendor, slug) already exists."""
        # Arrange
        vendor = _make_vendor()
        existing = _make_product(vendor.id, "pan-os")
        service, _, _ = _make_service(
            vendor_get_by_slug=vendor,
            product_get_by_vendor_slug=existing,
        )
        request = ProductCreate(name="PAN-OS")

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.create(vendor.slug, request, current_user_id=uuid.uuid4())


class TestProductServiceListByVendor:
    """Tests for ProductService.list_by_vendor_slug()."""

    async def test_returns_products_for_vendor(self):
        """Should fetch vendor then products."""
        # Arrange
        vendor = _make_vendor()
        service, product_repo, _ = _make_service(vendor_get_by_slug=vendor)
        product_repo.list_by_vendor = AsyncMock(return_value=[_make_product(vendor.id)])

        # Act
        result = await service.list_by_vendor_slug(vendor.slug)

        # Assert
        assert len(result) == 1


class TestProductServiceUpdate:
    """Tests for ProductService.update()."""

    async def test_update_applies_changes(self):
        """Should apply update fields."""
        # Arrange
        product = _make_product(uuid.uuid4(), "pan-os")
        service, _, _ = _make_service(product_get_by_id=product)
        request = ProductUpdate(name="New Name")

        # Act
        result = await service.update(product.id, request)

        # Assert
        assert result.name == "New Name"


class TestProductServiceDelete:
    """Tests for ProductService.delete()."""

    async def test_deletes_product(self):
        """Should delete via repo."""
        # Arrange
        product = _make_product(uuid.uuid4())
        service, repo, _ = _make_service(product_get_by_id=product)

        # Act
        await service.delete(product.id)

        # Assert
        repo.delete.assert_awaited_once_with(product)
