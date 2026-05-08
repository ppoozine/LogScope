import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.product import Product
from app.modules.library.routers.product_router import get_product_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_product() -> Product:
    p = Product()
    p.id = uuid.uuid4()
    p.vendor_id = uuid.uuid4()
    p.name = "PAN-OS"
    p.slug = "pan-os"
    p.version = None
    p.description = None
    p.deploy_type = None
    p.category = "network"
    p.doc_url = None
    p.status = "active"
    p.created_at = datetime.now(UTC)
    p.updated_at = datetime.now(UTC)
    return p


def _make_product_detail():
    """Build a minimal ProductDetail for router test."""
    from app.modules.library.schemas import ProductDetail

    return ProductDetail(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        name="PAN-OS",
        slug="pan-os",
        version=None,
        description=None,
        deploy_type=None,
        category="network",
        doc_url=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        log_types=[],
    )


class TestProductListByVendor:
    """Tests for GET /api/v1/library/vendors/{vendor_slug}/products."""

    async def test_returns_products(self, app: FastAPI, client: AsyncClient):
        """Should return list scoped to vendor."""
        # Arrange
        fake = AsyncMock()
        fake.list_by_vendor_slug = AsyncMock(return_value=[_make_product()])
        app.dependency_overrides[get_product_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get("/api/v1/library/vendors/acme/products")

        # Assert
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1


class TestProductGet:
    """Tests for GET /api/v1/library/vendors/{vendor_slug}/products/{slug}."""

    async def test_returns_product(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with ProductDetail body (nested)."""
        # Arrange
        fake = AsyncMock()
        fake.get_detail = AsyncMock(return_value=_make_product_detail())
        app.dependency_overrides[get_product_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get("/api/v1/library/vendors/acme/products/pan-os")

        # Assert
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["slug"] == "pan-os"
        assert "log_types" in body["data"]


class TestProductCreate:
    """Tests for POST /api/v1/library/vendors/{vendor_slug}/products."""

    async def test_creates_product(self, app: FastAPI, client: AsyncClient):
        """Should return 201."""
        # Arrange
        fake = AsyncMock()
        fake.create = AsyncMock(return_value=_make_product())
        app.dependency_overrides[get_product_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            "/api/v1/library/vendors/acme/products",
            json={"name": "PAN-OS"},
        )

        # Assert
        assert r.status_code == 201


class TestProductUpdate:
    """Tests for PATCH /api/v1/library/products/{id}."""

    async def test_updates_product(self, app: FastAPI, client: AsyncClient):
        """Should return 200."""
        # Arrange
        fake = AsyncMock()
        fake.update = AsyncMock(return_value=_make_product())
        app.dependency_overrides[get_product_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.patch(
            f"/api/v1/library/products/{uuid.uuid4()}",
            json={"version": "v2"},
        )

        # Assert
        assert r.status_code == 200


class TestProductDelete:
    """Tests for DELETE /api/v1/library/products/{id}."""

    async def test_deletes_product(self, app: FastAPI, client: AsyncClient):
        """Should return 204."""
        # Arrange
        fake = AsyncMock()
        fake.delete = AsyncMock(return_value=None)
        app.dependency_overrides[get_product_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.delete(f"/api/v1/library/products/{uuid.uuid4()}")

        # Assert
        assert r.status_code == 204
