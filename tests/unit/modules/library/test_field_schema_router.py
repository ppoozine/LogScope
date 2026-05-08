import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.routers.field_schema_router import get_field_schema_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_field(name: str = "src_ip") -> FieldSchema:
    f = FieldSchema()
    f.id = uuid.uuid4()
    f.log_type_id = uuid.uuid4()
    f.field_name = name
    f.field_type = "ip"
    f.description = None
    f.is_required = False
    f.is_identifier = True
    f.example_value = None
    f.sort_order = 0
    return f


class TestFieldSchemaPut:
    """Tests for PUT /api/v1/library/log_types/{id}/fields."""

    async def test_replaces_fields(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with new fields."""
        # Arrange
        fake = AsyncMock()
        fake.replace_for_log_type = AsyncMock(return_value=[_make_field("src_ip")])
        app.dependency_overrides[get_field_schema_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.put(
            f"/api/v1/library/log_types/{uuid.uuid4()}/fields",
            json={"fields": [{"field_name": "src_ip", "field_type": "ip", "is_identifier": True}]},
        )

        # Assert
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1
