"""Router test for POST /api/v1/library/parse_rules/{id}/promote."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.common.exceptions import ConflictError, NotFoundError
from app.modules.auth.models.user import User
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.routers import parse_rule_router as prr


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _rule(status: str = "published") -> ParseRule:
    r = ParseRule()
    r.id = uuid.uuid4()
    r.log_type_id = uuid.uuid4()
    r.version = 2
    r.vrl_code = "."
    r.engine_version = "0.32"
    r.status = status
    r.created_at = datetime.now(UTC)
    r.updated_at = datetime.now(UTC)
    return r


class TestPromoteRoute:
    async def test_promote_success_returns_published_rule(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_service = AsyncMock()
        fake_service.promote = AsyncMock(return_value=_rule(status="published"))
        app.dependency_overrides[prr.get_parse_rule_service] = lambda: fake_service

        r = await client.post(f"/api/v1/library/parse_rules/{uuid.uuid4()}/promote")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["status"] == "published"

    async def test_promote_archived_returns_409(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_service = AsyncMock()
        fake_service.promote = AsyncMock(side_effect=ConflictError("archived"))
        app.dependency_overrides[prr.get_parse_rule_service] = lambda: fake_service

        r = await client.post(f"/api/v1/library/parse_rules/{uuid.uuid4()}/promote")
        assert r.status_code == 409

    async def test_promote_unknown_returns_404(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_service = AsyncMock()
        fake_service.promote = AsyncMock(side_effect=NotFoundError("nope"))
        app.dependency_overrides[prr.get_parse_rule_service] = lambda: fake_service

        r = await client.post(f"/api/v1/library/parse_rules/{uuid.uuid4()}/promote")
        assert r.status_code == 404
