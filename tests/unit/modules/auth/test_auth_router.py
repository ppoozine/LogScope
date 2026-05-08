from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user, get_auth_service
from app.modules.auth.models.user import User


class TestLoginRoute:
    """Tests for POST /api/v1/auth/login."""

    async def test_login_returns_session_cookie_on_success(self, app: FastAPI, client: AsyncClient):
        """Should set HttpOnly session cookie when login succeeds."""
        # Arrange
        fake_auth = AsyncMock()
        fake_auth.login = AsyncMock(return_value="sid-abc")
        app.dependency_overrides[get_auth_service] = lambda: fake_auth

        # Act
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "a@b.c", "password": "x"},
        )

        # Assert
        assert r.status_code == 200
        cookie = r.headers.get("set-cookie", "")
        assert "session=sid-abc" in cookie
        assert "HttpOnly" in cookie

    async def test_login_returns_401_on_invalid(self, app: FastAPI, client: AsyncClient):
        """Should map UnauthorizedError to 401."""
        # Arrange
        from app.common.exceptions import UnauthorizedError

        fake_auth = AsyncMock()
        fake_auth.login = AsyncMock(side_effect=UnauthorizedError("invalid credentials"))
        app.dependency_overrides[get_auth_service] = lambda: fake_auth

        # Act
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "a@b.c", "password": "x"},
        )

        # Assert
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"


class TestMeRoute:
    """Tests for GET /api/v1/auth/me."""

    async def test_me_returns_user(self, app: FastAPI, client: AsyncClient):
        """Should return current user when authenticated."""
        # Arrange
        import uuid
        from datetime import UTC, datetime

        u = User()
        u.id = uuid.uuid4()
        u.email = "me@x.y"
        u.display_name = "Me"
        u.is_active = True
        u.created_at = datetime.now(UTC)
        u.updated_at = datetime.now(UTC)

        app.dependency_overrides[current_user] = lambda: u

        # Act
        r = await client.get("/api/v1/auth/me")

        # Assert
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["email"] == "me@x.y"
        assert body["data"]["display_name"] == "Me"


class TestLogoutRoute:
    """Tests for POST /api/v1/auth/logout."""

    async def test_logout_clears_cookie(self, app: FastAPI, client: AsyncClient):
        """Should call AuthService.logout and clear cookie."""
        # Arrange
        fake_auth = AsyncMock()
        fake_auth.logout = AsyncMock(return_value=None)
        app.dependency_overrides[get_auth_service] = lambda: fake_auth
        client.cookies.set("session", "sid-abc")

        # Act
        r = await client.post("/api/v1/auth/logout")

        # Assert
        assert r.status_code == 200
        cookie = r.headers.get("set-cookie", "")
        assert "session=" in cookie
        assert "Max-Age=0" in cookie
        fake_auth.logout.assert_awaited_once_with("sid-abc")
