"""Read-only repository that flattens (vendor, product, log_type, sample)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analyzer.services.match_service import _CatalogRow
from app.modules.library.models.log_type import LogType
from app.modules.library.models.product import Product
from app.modules.library.models.sample_log import SampleLog
from app.modules.library.models.vendor import Vendor


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch_all(self) -> list[_CatalogRow]:
        """Return one row per LogType joined with vendor/product + first sample.

        Uses two queries (catalog + samples) and stitches in Python; for v1
        scale (<200 log types) this is fine. Future optimization: a single
        JOIN with row_number() to pick first sample.
        """
        stmt = (
            select(
                LogType.id,
                Vendor.slug,
                Product.slug,
                LogType.name,
                LogType.format,
            )
            .join(Product, Product.id == LogType.product_id)
            .join(Vendor, Vendor.id == Product.vendor_id)
            .order_by(Vendor.slug, Product.slug, LogType.name)
        )
        result = await self._session.execute(stmt)
        base = result.all()

        sample_stmt = select(SampleLog.log_type_id, SampleLog.raw_log).order_by(
            SampleLog.log_type_id, SampleLog.created_at.desc()
        )
        sample_result = await self._session.execute(sample_stmt)
        sample_rows = sample_result.all()
        first_sample: dict[str, str] = {}
        for log_type_id, raw_log in sample_rows:
            key = str(log_type_id)
            if key not in first_sample:
                first_sample[key] = raw_log

        return [
            _CatalogRow(
                log_type_id=lt_id,
                vendor_slug=vendor_slug,
                product_slug=product_slug,
                log_type_name=lt_name,
                format=lt_format,
                sample=first_sample.get(str(lt_id)),
            )
            for (lt_id, vendor_slug, product_slug, lt_name, lt_format) in base
        ]
