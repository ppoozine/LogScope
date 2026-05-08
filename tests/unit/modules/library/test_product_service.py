import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.models.log_type import LogType
from app.modules.library.models.product import Product
from app.modules.library.models.sample_log import SampleLog
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


def _make_log_type_for_detail(product_id: uuid.UUID) -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = product_id
    lt.name = "Traffic"
    lt.slug = "traffic"
    lt.format = "csv"
    lt.transport = None
    lt.status = "draft"
    lt.source = "manual"
    lt.current_parse_rule_id = None
    lt.description = None
    lt.published_at = None
    lt.created_at = datetime.now(UTC)
    lt.updated_at = datetime.now(UTC)
    return lt


class TestProductServiceGetDetail:
    """Tests for ProductService.get_detail()."""

    async def test_returns_full_nested_detail(self):
        """Should aggregate product + log_types + fields + samples + current_rule."""
        # Arrange
        vendor = _make_vendor()
        product = _make_product(vendor.id, "pan-os")
        product.created_at = datetime.now(UTC)
        product.updated_at = datetime.now(UTC)
        product.version = None
        product.description = None
        product.deploy_type = None
        product.doc_url = None
        product.status = "active"

        lt = _make_log_type_for_detail(product.id)

        field = FieldSchema()
        field.id = uuid.uuid4()
        field.log_type_id = lt.id
        field.field_name = "src_ip"
        field.field_type = "ip"
        field.description = None
        field.is_required = False
        field.is_identifier = True
        field.example_value = None
        field.sort_order = 0

        sample = SampleLog()
        sample.id = uuid.uuid4()
        sample.log_type_id = lt.id
        sample.raw_log = "1,2,3"
        sample.label = "normal"
        sample.description = None
        sample.created_at = datetime.now(UTC)

        vendor_repo = MagicMock()
        vendor_repo.get_by_slug = AsyncMock(return_value=vendor)

        product_repo = MagicMock()
        product_repo.get_by_vendor_and_slug = AsyncMock(return_value=product)

        log_type_repo = MagicMock()
        log_type_repo.list_by_product = AsyncMock(return_value=[lt])

        field_repo = MagicMock()
        field_repo.list_by_log_type = AsyncMock(return_value=[field])

        parse_rule_repo = MagicMock()
        parse_rule_repo.get_by_id = AsyncMock(return_value=None)

        sample_repo = MagicMock()
        sample_repo.list_by_log_type = AsyncMock(return_value=[sample])

        service = ProductService(
            product_repo,
            vendor_repo,
            log_type_repo,
            field_repo,
            parse_rule_repo,
            sample_repo,
        )

        # Act
        result = await service.get_detail(vendor.slug, product.slug)

        # Assert
        assert result.slug == "pan-os"
        assert len(result.log_types) == 1
        assert len(result.log_types[0].fields) == 1
        assert result.log_types[0].fields[0].field_name == "src_ip"
        assert result.log_types[0].current_parse_rule is None
        assert len(result.log_types[0].samples) == 1
