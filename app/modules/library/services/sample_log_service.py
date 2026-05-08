import uuid

from app.common.exceptions import NotFoundError
from app.modules.library.models.sample_log import SampleLog
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.sample_log_repository import SampleLogRepository
from app.modules.library.schemas import SampleLogCreate


class SampleLogService:
    def __init__(
        self,
        sample_repo: SampleLogRepository,
        log_type_repo: LogTypeRepository,
    ) -> None:
        self._samples = sample_repo
        self._log_types = log_type_repo

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[SampleLog]:
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")
        return await self._samples.list_by_log_type(log_type_id)

    async def create(
        self,
        log_type_id: uuid.UUID,
        data: SampleLogCreate,
        *,
        current_user_id: uuid.UUID,
    ) -> SampleLog:
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")

        sample = SampleLog()
        sample.log_type_id = log_type_id
        sample.raw_log = data.raw_log
        sample.label = data.label
        sample.description = data.description
        sample.added_by = current_user_id
        return await self._samples.create(sample)

    async def delete(self, sample_id: uuid.UUID) -> None:
        sample = await self._samples.get_by_id(sample_id)
        if sample is None:
            raise NotFoundError(f"sample not found: {sample_id}")
        await self._samples.delete(sample)
