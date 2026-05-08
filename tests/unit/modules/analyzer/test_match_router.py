"""Router tests for POST /api/v1/analyzer/match."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.analyzer.routers.match_router import get_match_service
from app.modules.analyzer.schemas import MatchCandidate, MatchResponse
from app.modules.auth.models.user import User


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


class TestMatchRoute:
    """Tests for POST /api/v1/analyzer/match."""

    async def test_returns_candidates(self, app: FastAPI, client: AsyncClient):
        """Should pipe service result into DataResponse."""
        # Arrange
        candidate = MatchCandidate(
            vendor_slug="palo-alto",
            product_slug="pan-os",
            log_type_id=uuid.uuid4(),
            log_type_name="Traffic",
            confidence=0.92,
            reason="符合 PAN-OS CSV 格式",
        )
        fake = AsyncMock()
        fake.match = AsyncMock(return_value=MatchResponse(candidates=[candidate]))
        app.dependency_overrides[get_match_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            "/api/v1/analyzer/match",
            json={"raw_log": "1,2,3", "top_k": 3},
        )

        # Assert
        assert r.status_code == 200
        body = r.json()["data"]
        assert len(body["candidates"]) == 1
        assert body["candidates"][0]["confidence"] == 0.92

    async def test_returns_empty_when_no_api_key(self, app: FastAPI, client: AsyncClient):
        """Match service returns empty (no key) → still 200, empty candidates."""
        # Arrange
        fake = AsyncMock()
        fake.match = AsyncMock(return_value=MatchResponse(candidates=[]))
        app.dependency_overrides[get_match_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            "/api/v1/analyzer/match",
            json={"raw_log": "x", "top_k": 3},
        )

        # Assert
        assert r.status_code == 200
        assert r.json()["data"]["candidates"] == []

    async def test_requires_auth(self, app: FastAPI, client: AsyncClient):
        """Should 401 when session is missing."""
        from app.common.auth import get_auth_service
        from app.common.exceptions import UnauthorizedError

        # Arrange: fake auth raises UnauthorizedError (no session cookie)
        fake_auth = AsyncMock()
        fake_auth.get_current_user_from_session = AsyncMock(side_effect=UnauthorizedError("missing session"))
        app.dependency_overrides[get_auth_service] = lambda: fake_auth
        # Also override get_match_service so DB is not needed before auth check
        fake_service = AsyncMock()
        app.dependency_overrides[get_match_service] = lambda: fake_service

        # Act
        r = await client.post(
            "/api/v1/analyzer/match",
            json={"raw_log": "x", "top_k": 3},
        )

        # Assert
        assert r.status_code == 401
