import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.log_type import LogType
from app.modules.library.routers.log_type_router import (
    get_field_schema_service,
    get_log_type_service,
    get_parse_rule_service,
    get_sample_log_service,
)


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


class TestLogTypeGet:
    """Tests for GET /api/v1/library/log_types/{log_type_id}."""

    async def test_returns_log_type_detail(self, app: FastAPI, client: AsyncClient):
        """Should return LogTypeDetail with fields/current_parse_rule/samples."""
        # Arrange
        log_type = _make_log_type()
        fake_service = AsyncMock()
        fake_service.get_by_id = AsyncMock(return_value=log_type)
        fake_field_service = AsyncMock()
        fake_field_service.list_by_log_type = AsyncMock(return_value=[])
        fake_parse_service = AsyncMock()
        fake_parse_service.get_by_id = AsyncMock(return_value=None)
        fake_sample_service = AsyncMock()
        fake_sample_service.list_by_log_type = AsyncMock(return_value=[])

        app.dependency_overrides[get_log_type_service] = lambda: fake_service
        app.dependency_overrides[get_field_schema_service] = lambda: fake_field_service
        app.dependency_overrides[get_parse_rule_service] = lambda: fake_parse_service
        app.dependency_overrides[get_sample_log_service] = lambda: fake_sample_service
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get(f"/api/v1/library/log_types/{log_type.id}")

        # Assert
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["id"] == str(log_type.id)
        assert "fields" in data
        assert "current_parse_rule" in data
        assert "samples" in data
        assert data["fields"] == []
        assert data["current_parse_rule"] is None
        assert data["samples"] == []


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
