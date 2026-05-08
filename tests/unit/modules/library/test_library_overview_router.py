import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.routers.library_overview_router import (
    get_library_overview_service,
)
from app.modules.library.schemas import (
    LogTypeCounts,
    OverviewProduct,
    OverviewVendor,
    OverviewVendorGroup,
)


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


class TestLibraryOverviewRoute:
    """Tests for GET /api/v1/library/overview."""

    async def test_returns_grouped_response(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with vendor groups."""
        # Arrange
        sample = [
            OverviewVendorGroup(
                vendor=OverviewVendor(
                    id=uuid.uuid4(),
                    name="Acme",
                    slug="acme",
                    logo_url=None,
                ),
                products=[
                    OverviewProduct(
                        id=uuid.uuid4(),
                        name="P",
                        slug="p",
                        category="network",
                        status="active",
                        log_type_counts=LogTypeCounts(total=0, published=0, draft=0),
                        is_empty=True,
                    )
                ],
            )
        ]
        fake = AsyncMock()
        fake.overview = AsyncMock(return_value=sample)
        app.dependency_overrides[get_library_overview_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get("/api/v1/library/overview")

        # Assert
        assert r.status_code == 200
        body = r.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["vendor"]["slug"] == "acme"
        assert body["data"][0]["products"][0]["is_empty"] is True

    async def test_overview_passes_q_query_param(self, app: FastAPI, client: AsyncClient):
        """Should pass `?q=...` through to service.overview(q=...)."""
        # Arrange
        fake = AsyncMock()
        fake.overview = AsyncMock(return_value=[])
        app.dependency_overrides[get_library_overview_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get("/api/v1/library/overview?q=palo")

        # Assert
        assert r.status_code == 200
        fake.overview.assert_awaited_once()
        kwargs = fake.overview.await_args.kwargs
        assert kwargs.get("q") == "palo"
