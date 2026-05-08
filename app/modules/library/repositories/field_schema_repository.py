import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.field_schema import FieldSchema


class FieldSchemaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[FieldSchema]:
        stmt = (
            select(FieldSchema)
            .where(FieldSchema.log_type_id == log_type_id)
            .order_by(FieldSchema.sort_order, FieldSchema.field_name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def replace_for_log_type(
        self,
        log_type_id: uuid.UUID,
        items: list[FieldSchema],
    ) -> list[FieldSchema]:
        """Atomically delete existing fields for log_type then insert new ones."""
        await self._session.execute(delete(FieldSchema).where(FieldSchema.log_type_id == log_type_id))
        for item in items:
            self._session.add(item)
        await self._session.flush()
        for item in items:
            await self._session.refresh(item)
        return items
