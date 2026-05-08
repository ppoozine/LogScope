import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.vendor import Vendor
from app.modules.library.routers.vendor_router import get_vendor_service


def _logged_in_user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "test@x.y"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_vendor(slug: str = "acme") -> Vendor:
    v = Vendor()
    v.id = uuid.uuid4()
    v.name = "Acme"
    v.slug = slug
    v.website_url = None
    v.logo_url = None
    v.status = "active"
    v.created_at = datetime.now(UTC)
    v.updated_at = datetime.now(UTC)
    return v


class TestVendorList:
    """Tests for GET /api/v1/library/vendors."""

    async def test_returns_vendor_list(self, app: FastAPI, client: AsyncClient):
        """Should return paginated list of vendors."""
        # Arrange
        fake_service = AsyncMock()
        fake_service.list = AsyncMock(return_value=[_make_vendor("a"), _make_vendor("b")])
        app.dependency_overrides[get_vendor_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _logged_in_user

        # Act
        r = await client.get("/api/v1/library/vendors")

        # Assert
        assert r.status_code == 200
        body = r.json()
        assert len(body["data"]) == 2

    async def test_requires_auth(self, app: FastAPI, client: AsyncClient):
        """Should 401 when not logged in."""
        from app.common.auth import get_auth_service
        from app.common.exceptions import UnauthorizedError

        # Arrange: fake auth raises UnauthorizedError (no session cookie),
        # also override get_vendor_service to avoid DB-not-initialized error
        fake_auth = AsyncMock()
        fake_auth.get_current_user_from_session = AsyncMock(
            side_effect=UnauthorizedError("missing session")
        )
        fake_service = AsyncMock()
        app.dependency_overrides[get_auth_service] = lambda: fake_auth
        app.dependency_overrides[get_vendor_service] = lambda: fake_service

        # Act
        r = await client.get("/api/v1/library/vendors")

        # Assert
        assert r.status_code == 401


class TestVendorGet:
    """Tests for GET /api/v1/library/vendors/{slug}."""

    async def test_returns_vendor_when_found(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with vendor body."""
        # Arrange
        target = _make_vendor("acme")
        fake_service = AsyncMock()
        fake_service.get_by_slug = AsyncMock(return_value=target)
        app.dependency_overrides[get_vendor_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _logged_in_user

        # Act
        r = await client.get("/api/v1/library/vendors/acme")

        # Assert
        assert r.status_code == 200
        assert r.json()["data"]["slug"] == "acme"

    async def test_returns_404_when_missing(self, app: FastAPI, client: AsyncClient):
        """Should return 404 when service raises NotFoundError."""
        # Arrange
        from app.common.exceptions import NotFoundError

        fake_service = AsyncMock()
        fake_service.get_by_slug = AsyncMock(side_effect=NotFoundError("vendor not found"))
        app.dependency_overrides[get_vendor_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _logged_in_user

        # Act
        r = await client.get("/api/v1/library/vendors/missing")

        # Assert
        assert r.status_code == 404


class TestVendorCreate:
    """Tests for POST /api/v1/library/vendors."""

    async def test_creates_vendor(self, app: FastAPI, client: AsyncClient):
        """Should accept body and return 201 with created vendor."""
        # Arrange
        created = _make_vendor("acme")
        fake_service = AsyncMock()
        fake_service.create = AsyncMock(return_value=created)
        app.dependency_overrides[get_vendor_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _logged_in_user

        # Act
        r = await client.post(
            "/api/v1/library/vendors",
            json={"name": "Acme"},
        )

        # Assert
        assert r.status_code == 201
        assert r.json()["data"]["slug"] == "acme"


class TestVendorDelete:
    """Tests for DELETE /api/v1/library/vendors/{id}."""

    async def test_deletes_vendor(self, app: FastAPI, client: AsyncClient):
        """Should return 204 on success."""
        # Arrange
        fake_service = AsyncMock()
        fake_service.delete = AsyncMock(return_value=None)
        app.dependency_overrides[get_vendor_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _logged_in_user

        # Act
        r = await client.delete(f"/api/v1/library/vendors/{uuid.uuid4()}")

        # Assert
        assert r.status_code == 204
