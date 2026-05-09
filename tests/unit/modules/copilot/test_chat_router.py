"""Router tests for POST /api/v1/copilot/chat."""

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


async def _fake_stream_gen():
    yield b"event: text_delta\ndata: {\"text\":\"hi\"}\n\n"
    yield b"event: done\ndata: {}\n\n"


class TestChatRoute:
    async def test_returns_event_stream(self, app: FastAPI, client: AsyncClient):
        from app.modules.copilot.routers.chat_router import get_chat_service

        # Arrange
        fake = AsyncMock()
        fake.stream = lambda **kwargs: _fake_stream_gen()
        app.dependency_overrides[get_chat_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            "/api/v1/copilot/chat",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "skill": "log_explain",
            },
        )

        # Assert
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        body = r.text
        assert "event: text_delta" in body
        assert "event: done" in body

    async def test_requires_auth(self, app: FastAPI, client: AsyncClient):
        from app.common.auth import get_auth_service
        from app.common.exceptions import UnauthorizedError
        from app.modules.copilot.routers.chat_router import get_chat_service

        # Arrange
        fake_auth = AsyncMock()
        fake_auth.get_current_user_from_session = AsyncMock(
            side_effect=UnauthorizedError("missing session")
        )
        app.dependency_overrides[get_auth_service] = lambda: fake_auth
        app.dependency_overrides[get_chat_service] = lambda: AsyncMock()

        # Act
        r = await client.post(
            "/api/v1/copilot/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

        # Assert
        assert r.status_code == 401

    async def test_rejects_when_last_message_not_user(
        self, app: FastAPI, client: AsyncClient
    ):
        from app.modules.copilot.routers.chat_router import get_chat_service

        # Arrange
        app.dependency_overrides[current_user] = _user
        app.dependency_overrides[get_chat_service] = lambda: AsyncMock()

        # Act
        r = await client.post(
            "/api/v1/copilot/chat",
            json={
                "messages": [
                    {"role": "user", "content": "hi"},
                    {"role": "assistant", "content": "hello"},
                ],
            },
        )

        # Assert
        assert r.status_code == 422
        assert "user" in r.json()["detail"][0]["msg"].lower()

    async def test_rejects_empty_messages(self, app: FastAPI, client: AsyncClient):
        from app.modules.copilot.routers.chat_router import get_chat_service

        # Arrange
        app.dependency_overrides[current_user] = _user
        app.dependency_overrides[get_chat_service] = lambda: AsyncMock()

        # Act
        r = await client.post(
            "/api/v1/copilot/chat", json={"messages": []}
        )

        # Assert
        assert r.status_code == 422

    async def test_rejects_too_many_messages(
        self, app: FastAPI, client: AsyncClient
    ):
        from app.modules.copilot.routers.chat_router import get_chat_service

        # Arrange
        app.dependency_overrides[current_user] = _user
        app.dependency_overrides[get_chat_service] = lambda: AsyncMock()

        # Act
        r = await client.post(
            "/api/v1/copilot/chat",
            json={
                "messages": [{"role": "user", "content": "x"}] * 41,
            },
        )

        # Assert
        assert r.status_code == 422
