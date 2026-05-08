import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.sample_log import SampleLog


class SampleLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, sample_id: uuid.UUID) -> SampleLog | None:
        result = await self._session.execute(
            select(SampleLog).where(SampleLog.id == sample_id)
        )
        return result.scalar_one_or_none()

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[SampleLog]:
        stmt = (
            select(SampleLog)
            .where(SampleLog.log_type_id == log_type_id)
            .order_by(SampleLog.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, sample: SampleLog) -> SampleLog:
        self._session.add(sample)
        await self._session.flush()
        await self._session.refresh(sample)
        return sample

    async def delete(self, sample: SampleLog) -> None:
        await self._session.delete(sample)
        await self._session.flush()
