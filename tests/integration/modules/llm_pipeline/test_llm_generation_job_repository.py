"""Integration tests for LlmGenerationJobRepository — exercises the 3-tx
audit pattern against real Postgres."""

import uuid
from datetime import UTC, datetime

import pytest

# Import all FK target models so SQLAlchemy can resolve relationships
# (LlmGenerationJob has FKs to users, log_types, parse_rules).
from app.modules.auth.models.user import User  # noqa: F401
from app.modules.library.models import LogType, ParseRule  # noqa: F401
from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.llm_pipeline.models import Doc, LlmGenerationJob
from app.modules.llm_pipeline.repositories.llm_generation_job_repository import (
    LlmGenerationJobRepository,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _seed(db_session) -> tuple[Vendor, Product, Doc]:
    v = Vendor(
        id=uuid.uuid4(),
        name="x",
        slug=f"v-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db_session.add(v)
    await db_session.flush()
    p = Product(
        id=uuid.uuid4(),
        vendor_id=v.id,
        name="p",
        slug=f"p-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db_session.add(p)
    await db_session.flush()
    d = Doc(
        id=uuid.uuid4(),
        vendor_id=v.id,
        content="x",
        content_format="markdown",
        fetched_at=datetime.now(UTC),
        fetched_by="manual",
    )
    db_session.add(d)
    await db_session.flush()
    await db_session.commit()
    return v, p, d


class TestJobRepository:
    async def test_create_pending_returns_id_and_persists(
        self, db_session, db_session_factory,
    ):
        _, p, d = await _seed(db_session)
        repo = LlmGenerationJobRepository(db_session_factory)
        job_id = await repo.create_pending(
            doc_id=d.id,
            product_id=p.id,
            requested_by=None,
            model="claude-opus-4-7",
        )
        async with db_session_factory() as s:
            job = await s.get(LlmGenerationJob, job_id)
            assert job is not None
            assert job.status == "pending"
            assert job.model == "claude-opus-4-7"

    async def test_finish_succeeded_sets_lineage(
        self, db_session, db_session_factory,
    ):
        _, p, d = await _seed(db_session)
        repo = LlmGenerationJobRepository(db_session_factory)
        job_id = await repo.create_pending(
            doc_id=d.id,
            product_id=p.id,
            requested_by=None,
            model="m",
        )
        await repo.finish_succeeded(
            job_id,
            log_type_id=None,
            parse_rule_id=None,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=10,
        )
        async with db_session_factory() as s:
            job = await s.get(LlmGenerationJob, job_id)
            assert job is not None
            assert job.status == "succeeded"
            assert job.input_tokens == 100
            assert job.output_tokens == 50
            assert job.cache_read_tokens == 10
            assert job.finished_at is not None

    async def test_finish_failed_records_error(
        self, db_session, db_session_factory,
    ):
        _, p, d = await _seed(db_session)
        repo = LlmGenerationJobRepository(db_session_factory)
        job_id = await repo.create_pending(
            doc_id=d.id,
            product_id=p.id,
            requested_by=None,
            model="m",
        )
        await repo.finish_failed(
            job_id,
            error_code="schema_mismatch",
            error_message="missing log_type",
            raw_response="<truncated 30 chars>",
        )
        async with db_session_factory() as s:
            job = await s.get(LlmGenerationJob, job_id)
            assert job is not None
            assert job.status == "failed"
            assert job.error_code == "schema_mismatch"
            assert job.error_message == "missing log_type"
            assert job.raw_response == "<truncated 30 chars>"

    async def test_finish_succeeded_on_missing_job_is_noop(
        self, db_session_factory,
    ):
        repo = LlmGenerationJobRepository(db_session_factory)
        await repo.finish_succeeded(
            uuid.uuid4(),
            log_type_id=None,
            parse_rule_id=None,
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
        )

    async def test_finish_failed_on_missing_job_is_noop(self, db_session_factory):
        repo = LlmGenerationJobRepository(db_session_factory)
        await repo.finish_failed(
            uuid.uuid4(),
            error_code="anthropic_failed",
            error_message="x",
            raw_response=None,
        )
