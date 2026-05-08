import os

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestAuthFlow:
    """End-to-end auth flow against real Postgres + Redis."""

    async def test_login_then_me_then_logout(self, client: AsyncClient) -> None:
        """Should log in, fetch /me, then log out and reject /me."""
        # Arrange
        email = os.environ["LOGSCOPE_ADMIN_EMAIL"]
        password = os.environ["LOGSCOPE_ADMIN_PASSWORD"]

        # Act 1: login
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )

        # Assert 1
        assert r.status_code == 200, r.text
        assert "session" in client.cookies

        # Act 2: me
        r = await client.get("/api/v1/auth/me")

        # Assert 2
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["email"] == email

        # Act 3: logout
        r = await client.post("/api/v1/auth/logout")

        # Assert 3
        assert r.status_code == 200

        # Act 4: me (now unauthorized)
        r = await client.get("/api/v1/auth/me")

        # Assert 4
        assert r.status_code == 401

    async def test_login_with_wrong_password_rejected(self, client: AsyncClient) -> None:
        """Should return 401 for wrong password."""
        # Arrange
        email = os.environ["LOGSCOPE_ADMIN_EMAIL"]

        # Act
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "definitely-wrong"},
        )

        # Assert
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"
