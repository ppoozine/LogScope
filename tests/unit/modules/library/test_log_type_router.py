import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.log_type import LogType
from app.modules.library.routers.log_type_router import get_log_type_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_log_type() -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = uuid.uuid4()
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


class TestLogTypeListByProduct:
    """Tests for GET /api/v1/library/products/{product_id}/log_types."""

    async def test_returns_log_types(self, app: FastAPI, client: AsyncClient):
        """Should return scoped list."""
        # Arrange
        fake = AsyncMock()
        fake.list_by_product = AsyncMock(return_value=[_make_log_type()])
        app.dependency_overrides[get_log_type_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get(f"/api/v1/library/products/{uuid.uuid4()}/log_types")

        # Assert
        assert r.status_code == 200


class TestLogTypeCreate:
    """Tests for POST /api/v1/library/products/{product_id}/log_types."""

    async def test_creates(self, app: FastAPI, client: AsyncClient):
        """Should return 201."""
        # Arrange
        fake = AsyncMock()
        fake.create = AsyncMock(return_value=_make_log_type())
        app.dependency_overrides[get_log_type_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            f"/api/v1/library/products/{uuid.uuid4()}/log_types",
            json={"name": "Traffic", "format": "csv"},
        )

        # Assert
        assert r.status_code == 201


class TestLogTypePublish:
    """Tests for POST /api/v1/library/log_types/{id}/publish."""

    async def test_publishes(self, app: FastAPI, client: AsyncClient):
        """Should return 200."""
        # Arrange
        published = _make_log_type()
        published.status = "published"
        published.published_at = datetime.now(UTC)
        fake = AsyncMock()
        fake.publish = AsyncMock(return_value=published)
        app.dependency_overrides[get_log_type_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(f"/api/v1/library/log_types/{uuid.uuid4()}/publish")

        # Assert
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "published"

    async def test_returns_409_on_already_published(self, app: FastAPI, client: AsyncClient):
        """Should map ConflictError to 409."""
        # Arrange
        from app.common.exceptions import ConflictError

        fake = AsyncMock()
        fake.publish = AsyncMock(side_effect=ConflictError("already published"))
        app.dependency_overrides[get_log_type_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(f"/api/v1/library/log_types/{uuid.uuid4()}/publish")

        # Assert
        assert r.status_code == 409
