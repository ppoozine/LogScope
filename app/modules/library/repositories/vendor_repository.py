import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.vendor import Vendor


class VendorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, vendor_id: uuid.UUID) -> Vendor | None:
        result = await self._session.execute(select(Vendor).where(Vendor.id == vendor_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Vendor | None:
        result = await self._session.execute(select(Vendor).where(Vendor.slug == slug))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        status: str | None = None,
        q: str | None = None,
    ) -> list[Vendor]:
        stmt = select(Vendor)
        if status is not None:
            stmt = stmt.where(Vendor.status == status)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(Vendor.name.ilike(pattern))
        stmt = stmt.order_by(Vendor.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, vendor: Vendor) -> Vendor:
        self._session.add(vendor)
        await self._session.flush()
        await self._session.refresh(vendor)
        return vendor

    async def update(self, vendor: Vendor) -> Vendor:
        await self._session.flush()
        await self._session.refresh(vendor)
        return vendor

    async def delete(self, vendor: Vendor) -> None:
        await self._session.delete(vendor)
        await self._session.flush()
