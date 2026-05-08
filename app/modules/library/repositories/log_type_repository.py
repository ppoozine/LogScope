import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.log_type import LogType


class LogTypeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, log_type_id: uuid.UUID) -> LogType | None:
        result = await self._session.execute(select(LogType).where(LogType.id == log_type_id))
        return result.scalar_one_or_none()

    async def get_by_product_and_slug(self, product_id: uuid.UUID, slug: str) -> LogType | None:
        result = await self._session.execute(
            select(LogType).where(LogType.product_id == product_id, LogType.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_by_product(self, product_id: uuid.UUID) -> list[LogType]:
        stmt = select(LogType).where(LogType.product_id == product_id).order_by(LogType.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, log_type: LogType) -> LogType:
        self._session.add(log_type)
        await self._session.flush()
        await self._session.refresh(log_type)
        return log_type

    async def update(self, log_type: LogType) -> LogType:
        await self._session.flush()
        await self._session.refresh(log_type)
        return log_type

    async def delete(self, log_type: LogType) -> None:
        await self._session.delete(log_type)
        await self._session.flush()

    async def list_ids_for_vendor_product(
        self, vendor_slug: str, product_slug: str
    ) -> list[uuid.UUID]:
        """Return all log_type ids under vendor/product (any status)."""
        from app.modules.library.models.product import Product
        from app.modules.library.models.vendor import Vendor

        stmt = (
            select(LogType.id)
            .join(Product, Product.id == LogType.product_id)
            .join(Vendor, Vendor.id == Product.vendor_id)
            .where(Vendor.slug == vendor_slug, Product.slug == product_slug)
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]
