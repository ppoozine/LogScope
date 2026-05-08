import uuid

from app.common.exceptions import NotFoundError
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.repositories.field_schema_repository import (
    FieldSchemaRepository,
)
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.schemas import FieldSchemaBulkReplace


class FieldSchemaService:
    def __init__(
        self,
        field_repo: FieldSchemaRepository,
        log_type_repo: LogTypeRepository,
    ) -> None:
        self._fields = field_repo
        self._log_types = log_type_repo

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[FieldSchema]:
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")
        return await self._fields.list_by_log_type(log_type_id)

    async def replace_for_log_type(
        self,
        log_type_id: uuid.UUID,
        data: FieldSchemaBulkReplace,
    ) -> list[FieldSchema]:
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")

        items: list[FieldSchema] = []
        for fi in data.fields:
            f = FieldSchema()
            f.log_type_id = log_type_id
            f.field_name = fi.field_name
            f.field_type = fi.field_type
            f.description = fi.description
            f.is_required = fi.is_required
            f.is_identifier = fi.is_identifier
            f.example_value = fi.example_value
            f.sort_order = fi.sort_order
            items.append(f)

        return await self._fields.replace_for_log_type(log_type_id, items)
