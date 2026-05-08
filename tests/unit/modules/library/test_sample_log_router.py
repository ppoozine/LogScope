import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.sample_log import SampleLog
from app.modules.library.routers.sample_log_router import get_sample_log_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_sample() -> SampleLog:
    s = SampleLog()
    s.id = uuid.uuid4()
    s.log_type_id = uuid.uuid4()
    s.raw_log = "1,2,3"
    s.label = "normal"
    s.description = None
    s.created_at = datetime.now(UTC)
    return s


class TestSampleCreate:
    """Tests for POST /api/v1/library/log_types/{id}/samples."""

    async def test_creates_sample(self, app: FastAPI, client: AsyncClient):
        """Should return 201."""
        # Arrange
        fake = AsyncMock()
        fake.create = AsyncMock(return_value=_make_sample())
        app.dependency_overrides[get_sample_log_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            f"/api/v1/library/log_types/{uuid.uuid4()}/samples",
            json={"raw_log": "1,2,3"},
        )

        # Assert
        assert r.status_code == 201


class TestSampleDelete:
    """Tests for DELETE /api/v1/library/samples/{id}."""

    async def test_deletes(self, app: FastAPI, client: AsyncClient):
        """Should return 204."""
        # Arrange
        fake = AsyncMock()
        fake.delete = AsyncMock(return_value=None)
        app.dependency_overrides[get_sample_log_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.delete(f"/api/v1/library/samples/{uuid.uuid4()}")

        # Assert
        assert r.status_code == 204
