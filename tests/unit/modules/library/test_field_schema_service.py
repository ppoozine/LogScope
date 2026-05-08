import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import NotFoundError
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.models.log_type import LogType
from app.modules.library.schemas import FieldSchemaBulkReplace, FieldSchemaItem
from app.modules.library.services.field_schema_service import FieldSchemaService


def _make_log_type() -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    return lt


def _make_field(name: str = "src_ip") -> FieldSchema:
    f = FieldSchema()
    f.id = uuid.uuid4()
    f.field_name = name
    f.field_type = "string"
    return f


def _make_service(*, log_type_get: LogType | None = None):
    field_repo = MagicMock()
    field_repo.list_by_log_type = AsyncMock(return_value=[])
    field_repo.replace_for_log_type = AsyncMock(
        side_effect=lambda lt_id, items: [_make_field(item.field_name) for item in items]
    )

    log_type_repo = MagicMock()
    log_type_repo.get_by_id = AsyncMock(return_value=log_type_get)

    return FieldSchemaService(field_repo, log_type_repo), field_repo, log_type_repo


class TestFieldSchemaServiceReplace:
    """Tests for FieldSchemaService.replace_for_log_type()."""

    async def test_replaces_fields(self):
        """Should call repo.replace_for_log_type with items."""
        # Arrange
        log_type = _make_log_type()
        service, field_repo, _ = _make_service(log_type_get=log_type)
        body = FieldSchemaBulkReplace(
            fields=[
                FieldSchemaItem(field_name="src_ip", field_type="ip", is_identifier=True),
                FieldSchemaItem(field_name="dst_ip", field_type="ip"),
            ]
        )

        # Act
        result = await service.replace_for_log_type(log_type.id, body)

        # Assert
        assert len(result) == 2
        field_repo.replace_for_log_type.assert_awaited_once()

    async def test_raises_not_found_when_log_type_missing(self):
        """Should raise NotFoundError."""
        # Arrange
        service, _, _ = _make_service(log_type_get=None)
        body = FieldSchemaBulkReplace(fields=[])

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.replace_for_log_type(uuid.uuid4(), body)


class TestFieldSchemaServiceList:
    """Tests for FieldSchemaService.list_by_log_type()."""

    async def test_returns_fields(self):
        """Should return repo result."""
        # Arrange
        log_type = _make_log_type()
        service, field_repo, _ = _make_service(log_type_get=log_type)
        field_repo.list_by_log_type = AsyncMock(return_value=[_make_field("a"), _make_field("b")])

        # Act
        result = await service.list_by_log_type(log_type.id)

        # Assert
        assert len(result) == 2
