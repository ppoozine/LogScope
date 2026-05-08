import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        result = await self._session.execute(select(Product).where(Product.id == product_id))
        return result.scalar_one_or_none()

    async def get_by_vendor_and_slug(self, vendor_id: uuid.UUID, slug: str) -> Product | None:
        result = await self._session.execute(
            select(Product).where(Product.vendor_id == vendor_id, Product.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_by_vendor(
        self,
        vendor_id: uuid.UUID,
        *,
        q: str | None = None,
    ) -> list[Product]:
        stmt = select(Product).where(Product.vendor_id == vendor_id)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(Product.name.ilike(pattern))
        stmt = stmt.order_by(Product.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, product: Product) -> Product:
        self._session.add(product)
        await self._session.flush()
        await self._session.refresh(product)
        return product

    async def update(self, product: Product) -> Product:
        await self._session.flush()
        await self._session.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        await self._session.delete(product)
        await self._session.flush()
