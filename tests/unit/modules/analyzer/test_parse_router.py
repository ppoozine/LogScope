"""Router tests for POST /api/v1/analyzer/parse."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


class TestParseRoute:
    """Tests for POST /api/v1/analyzer/parse."""

    async def test_parse_happy_path(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with results for valid VRL."""
        # Arrange
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            "/api/v1/analyzer/parse",
            json={
                "vrl_code": '.action = "allow"\n.',
                "logs": ["one"],
                "engine_version": "0.32",
            },
        )

        # Assert
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["kind"] == "ok"
        assert body["summary"]["success"] == 1

    async def test_parse_compile_error(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with kind=compile_error for invalid VRL."""
        # Arrange
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            "/api/v1/analyzer/parse",
            json={
                "vrl_code": "garbage",
                "logs": ["x"],
                "engine_version": "0.32",
            },
        )

        # Assert
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["kind"] == "compile_error"
        assert body["compile_error"]

    async def test_parse_too_many_logs_rejected(self, app: FastAPI, client: AsyncClient):
        """Should 422 when logs exceeds 500."""
        # Arrange
        app.dependency_overrides[current_user] = _user
        too_many = ["x"] * 501

        # Act
        r = await client.post(
            "/api/v1/analyzer/parse",
            json={
                "vrl_code": ".x = 1\n.",
                "logs": too_many,
                "engine_version": "0.32",
            },
        )

        # Assert
        assert r.status_code == 422

    async def test_parse_requires_auth(self, app: FastAPI, client: AsyncClient):
        """Should 401 without session."""
        from app.common.auth import get_auth_service
        from app.common.exceptions import UnauthorizedError

        # Arrange: fake auth raises UnauthorizedError (no session cookie)
        fake_auth = AsyncMock()
        fake_auth.get_current_user_from_session = AsyncMock(side_effect=UnauthorizedError("missing session"))
        app.dependency_overrides[get_auth_service] = lambda: fake_auth

        # Act
        r = await client.post(
            "/api/v1/analyzer/parse",
            json={
                "vrl_code": ".x = 1\n.",
                "logs": ["x"],
                "engine_version": "0.32",
            },
        )

        # Assert
        assert r.status_code == 401


class TestCheckRoute:
    """Tests for POST /api/v1/analyzer/check."""

    async def test_check_happy_path(self, app: FastAPI, client: AsyncClient):
        """Should return kind=ok for valid VRL."""
        # Arrange
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            "/api/v1/analyzer/check",
            json={"vrl_code": ".x = 1\n.", "engine_version": "0.32"},
        )

        # Assert
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["kind"] == "ok"

    async def test_check_compile_error(self, app: FastAPI, client: AsyncClient):
        """Should return kind=compile_error for invalid VRL."""
        # Arrange
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            "/api/v1/analyzer/check",
            json={"vrl_code": "garbage", "engine_version": "0.32"},
        )

        # Assert
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["kind"] == "compile_error"
        assert body["compile_error"]

    async def test_check_requires_auth(self, app: FastAPI, client: AsyncClient):
        """Should 401 without session."""
        from app.common.auth import get_auth_service
        from app.common.exceptions import UnauthorizedError

        # Arrange
        fake_auth = AsyncMock()
        fake_auth.get_current_user_from_session = AsyncMock(side_effect=UnauthorizedError("missing session"))
        app.dependency_overrides[get_auth_service] = lambda: fake_auth

        # Act
        r = await client.post(
            "/api/v1/analyzer/check",
            json={"vrl_code": ".x = 1\n.", "engine_version": "0.32"},
        )

        # Assert
        assert r.status_code == 401


class TestMatchAvailabilityRoute:
    """Tests for GET /api/v1/analyzer/match-availability."""

    async def test_reports_available_when_settings_have_key(self, app: FastAPI, client: AsyncClient):
        """Should report available=true when ANTHROPIC_API_KEY is set."""
        from app.core.config import Settings, get_settings

        # Arrange
        app.dependency_overrides[current_user] = _user
        app.dependency_overrides[get_settings] = lambda: Settings.model_construct(
            anthropic_api_key="sk-test", llm_match_model="m"
        )

        # Act
        r = await client.get("/api/v1/analyzer/match-availability")

        # Assert
        assert r.status_code == 200
        assert r.json()["data"]["available"] is True

    async def test_reports_unavailable_when_no_key(self, app: FastAPI, client: AsyncClient):
        """Should report available=false when key missing."""
        from app.core.config import Settings, get_settings

        # Arrange
        app.dependency_overrides[current_user] = _user
        app.dependency_overrides[get_settings] = lambda: Settings.model_construct(
            anthropic_api_key=None, llm_match_model="m"
        )

        # Act
        r = await client.get("/api/v1/analyzer/match-availability")

        # Assert
        assert r.status_code == 200
        assert r.json()["data"]["available"] is False


class TestFixturesRoute:
    """Tests for GET /api/v1/analyzer/fixtures."""

    async def test_lists_bundled_fixtures(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with bundled fixtures."""
        # Arrange
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get("/api/v1/analyzer/fixtures")

        # Assert
        assert r.status_code == 200
        body = r.json()["data"]
        ids = {f["id"] for f in body["fixtures"]}
        assert "simple-json" in ids
