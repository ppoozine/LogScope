"""Router tests for POST /api/v1/copilot/inline/vrl."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User

pytestmark = pytest.mark.asyncio


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


async def _fake_stream_gen():
    yield b"event: text_delta\ndata: {\"text\":\".dst_ip\"}\n\n"
    yield b"event: done\ndata: {}\n\n"


def _payload(**overrides):
    base = {
        "instruction": "加 dst_ip",
        "mode": "insert",
        "current_vrl": ". = parse_syslog!(.message)",
        "cursor_offset": 27,
        "vrl_engine": "0.32",
        "logs": ["log1"],
    }
    base.update(overrides)
    return base


class TestInlineRoute:
    async def test_returns_event_stream(self, app: FastAPI, client: AsyncClient):
        from app.modules.copilot.routers.chat_router import get_chat_service

        fake = AsyncMock()
        fake.stream_inline = lambda **kwargs: _fake_stream_gen()
        app.dependency_overrides[get_chat_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        r = await client.post("/api/v1/copilot/inline/vrl", json=_payload())

        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        body = r.text
        assert "event: text_delta" in body
        assert "event: done" in body

    async def test_requires_auth(self, app: FastAPI, client: AsyncClient):
        from app.common.auth import get_auth_service
        from app.common.exceptions import UnauthorizedError
        from app.modules.copilot.routers.chat_router import get_chat_service

        fake_auth = AsyncMock()
        fake_auth.get_current_user_from_session = AsyncMock(
            side_effect=UnauthorizedError("missing session")
        )
        app.dependency_overrides[get_auth_service] = lambda: fake_auth
        app.dependency_overrides[get_chat_service] = lambda: AsyncMock()

        r = await client.post("/api/v1/copilot/inline/vrl", json=_payload())

        assert r.status_code == 401

    async def test_rejects_missing_cursor_offset(
        self, app: FastAPI, client: AsyncClient
    ):
        from app.modules.copilot.routers.chat_router import get_chat_service

        app.dependency_overrides[get_chat_service] = lambda: AsyncMock()
        app.dependency_overrides[current_user] = _user

        bad = _payload()
        del bad["cursor_offset"]
        r = await client.post("/api/v1/copilot/inline/vrl", json=bad)

        assert r.status_code == 422

    async def test_rejects_replace_with_invalid_range(
        self, app: FastAPI, client: AsyncClient
    ):
        from app.modules.copilot.routers.chat_router import get_chat_service

        app.dependency_overrides[get_chat_service] = lambda: AsyncMock()
        app.dependency_overrides[current_user] = _user

        bad = _payload(
            mode="replace",
            cursor_offset=None,
            selection_start=5,
            selection_end=2,  # start >= end
        )
        # serialize: drop None to mimic FE behavior
        bad = {k: v for k, v in bad.items() if v is not None}
        r = await client.post("/api/v1/copilot/inline/vrl", json=bad)

        assert r.status_code == 422

    async def test_rejects_oversized_vrl(self, app: FastAPI, client: AsyncClient):
        from app.modules.copilot.routers.chat_router import get_chat_service

        app.dependency_overrides[get_chat_service] = lambda: AsyncMock()
        app.dependency_overrides[current_user] = _user

        r = await client.post(
            "/api/v1/copilot/inline/vrl",
            json=_payload(current_vrl="x" * 50_001, cursor_offset=0),
        )

        assert r.status_code == 422

    async def test_vrl_fix_returns_event_stream(
        self, app: FastAPI, client: AsyncClient
    ):
        from app.modules.copilot.routers.chat_router import get_chat_service

        fake = AsyncMock()
        fake.stream_inline = lambda **kwargs: _fake_stream_gen()
        app.dependency_overrides[get_chat_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        r = await client.post(
            "/api/v1/copilot/inline/vrl",
            json=_payload(
                skill="vrl_fix",
                mode="replace",
                cursor_offset=None,
                selection_start=0,
                selection_end=27,
                compile_error="error[E110]: foo",
            ),
        )

        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]

    async def test_vrl_fix_missing_compile_error(
        self, app: FastAPI, client: AsyncClient
    ):
        from app.modules.copilot.routers.chat_router import get_chat_service

        app.dependency_overrides[get_chat_service] = lambda: AsyncMock()
        app.dependency_overrides[current_user] = _user

        # vrl_fix without compile_error → 422
        bad = _payload(
            skill="vrl_fix",
            mode="replace",
            cursor_offset=None,
            selection_start=0,
            selection_end=27,
        )
        bad = {k: v for k, v in bad.items() if v is not None}
        r = await client.post("/api/v1/copilot/inline/vrl", json=bad)

        assert r.status_code == 422
