"""Job repository implementing the 3-transaction pattern from spec §3.4.

Each public method opens its own session+transaction via the project's
async_sessionmaker. This decouples audit writes from the surrounding
library-write transaction so the job row survives even when the library
write rolls back.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.llm_pipeline.models import LlmGenerationJob


class LlmGenerationJobRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_pending(
        self,
        *,
        doc_id: uuid.UUID,
        product_id: uuid.UUID,
        requested_by: uuid.UUID | None,
        model: str,
    ) -> uuid.UUID:
        job = LlmGenerationJob(
            id=uuid.uuid4(),
            doc_id=doc_id,
            product_id=product_id,
            requested_by=requested_by,
            status="pending",
            model=model,
            started_at=datetime.now(UTC),
        )
        async with self._session_factory() as session:
            async with session.begin():
                session.add(job)
        return job.id

    async def finish_succeeded(
        self,
        job_id: uuid.UUID,
        *,
        log_type_id: uuid.UUID | None,
        parse_rule_id: uuid.UUID | None,
        input_tokens: int | None,
        output_tokens: int | None,
        cache_read_tokens: int | None,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                job = await session.get(LlmGenerationJob, job_id)
                if job is None:
                    return
                job.status = "succeeded"
                job.log_type_id = log_type_id
                job.parse_rule_id = parse_rule_id
                job.input_tokens = input_tokens
                job.output_tokens = output_tokens
                job.cache_read_tokens = cache_read_tokens
                job.finished_at = datetime.now(UTC)

    async def finish_failed(
        self,
        job_id: uuid.UUID,
        *,
        error_code: str,
        error_message: str,
        raw_response: str | None,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                job = await session.get(LlmGenerationJob, job_id)
                if job is None:
                    return
                job.status = "failed"
                job.error_code = error_code
                job.error_message = error_message
                job.raw_response = raw_response
                job.finished_at = datetime.now(UTC)
