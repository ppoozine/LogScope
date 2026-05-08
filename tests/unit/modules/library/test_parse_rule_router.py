import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.routers.parse_rule_router import get_parse_rule_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_rule() -> ParseRule:
    pr = ParseRule()
    pr.id = uuid.uuid4()
    pr.log_type_id = uuid.uuid4()
    pr.version = 1
    pr.vrl_code = "."
    pr.engine_version = "0.32"
    pr.status = "draft"
    pr.notes = None
    pr.created_at = datetime.now(UTC)
    pr.updated_at = datetime.now(UTC)
    return pr


class TestParseRuleCreate:
    """Tests for POST /api/v1/library/log_types/{id}/parse_rules."""

    async def test_creates_draft(self, app: FastAPI, client: AsyncClient):
        """Should return 201 with new draft."""
        # Arrange
        fake = AsyncMock()
        fake.create_draft = AsyncMock(return_value=_make_rule())
        app.dependency_overrides[get_parse_rule_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            f"/api/v1/library/log_types/{uuid.uuid4()}/parse_rules",
            json={"vrl_code": ".", "engine_version": "0.32"},
        )

        # Assert
        assert r.status_code == 201


class TestParseRuleUpdate:
    """Tests for PATCH /api/v1/library/parse_rules/{id}."""

    async def test_updates_draft(self, app: FastAPI, client: AsyncClient):
        """Should return 200."""
        # Arrange
        fake = AsyncMock()
        fake.update = AsyncMock(return_value=_make_rule())
        app.dependency_overrides[get_parse_rule_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.patch(
            f"/api/v1/library/parse_rules/{uuid.uuid4()}",
            json={"vrl_code": "new"},
        )

        # Assert
        assert r.status_code == 200

    async def test_returns_409_on_published(self, app: FastAPI, client: AsyncClient):
        """Should map ConflictError to 409."""
        # Arrange
        from app.common.exceptions import ConflictError

        fake = AsyncMock()
        fake.update = AsyncMock(side_effect=ConflictError("immutable"))
        app.dependency_overrides[get_parse_rule_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.patch(
            f"/api/v1/library/parse_rules/{uuid.uuid4()}",
            json={"vrl_code": "new"},
        )

        # Assert
        assert r.status_code == 409
