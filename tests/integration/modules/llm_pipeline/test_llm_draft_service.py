"""Integration tests for LlmDraftService — exercises the 3-tx orchestration
pattern against real Postgres. Anthropic + VRL validator are mocked."""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.exceptions import NotFoundError

# Import all FK target models so SQLAlchemy can resolve relationships.
from app.modules.auth.models.user import User  # noqa: F401
from app.modules.library.models import LogType, ParseRule
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.llm_pipeline.exceptions import (
    AnthropicCallError,
    SchemaMismatchError,
    VrlCompileError,
)
from app.modules.llm_pipeline.models import Doc, LlmGenerationJob
from app.modules.llm_pipeline.repositories.llm_generation_job_repository import (
    LlmGenerationJobRepository,
)
from app.modules.llm_pipeline.services.llm_draft_service import LlmDraftService

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Module-level test helpers
# ---------------------------------------------------------------------------


def _good_tool_input(field_name: str = "src_ip") -> dict:
    return {
        "log_type": {
            "name": "PAN-OS TRAFFIC",
            "format": "syslog",
            "transport": "syslog_udp",
            "description": None,
        },
        "fields": [
            {
                "field_name": field_name,
                "field_type": "ip",
                "is_required": True,
                "is_identifier": False,
                "description": None,
                "example_value": None,
            },
        ],
        "vrl_code": (
            ". = parse_syslog!(.message)\n"
            f".{field_name} = parts[6] ?? null"
        ),
        "engine_version": "0.32",
        "notes": "ok",
    }


def _fake_anthropic_response(
    tool_input: dict,
    *,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_read: int = 10,
) -> SimpleNamespace:
    block = SimpleNamespace(
        type="tool_use", name="submit_draft", id="t1", input=tool_input,
    )
    usage = SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
    )
    return SimpleNamespace(
        content=[block],
        stop_reason="tool_use",
        usage=usage,
        model_dump=lambda: {"id": "msg1"},
    )


class _FakeAnthropic:
    """Minimal stand-in for the Anthropic async client.

    Either yields a precomputed response or raises a precomputed exception
    when ``messages.create`` is awaited.
    """

    def __init__(self, response_or_exc: Any) -> None:
        self._target = response_or_exc
        self.messages = self

    async def create(self, **_kwargs: Any) -> Any:
        if isinstance(self._target, Exception):
            raise self._target
        return self._target


def _noop_validator(code: str, *, engine_version: str) -> None:
    """Default vrl validator that accepts any code."""
    return None


async def _seed_minimal(db_session: AsyncSession) -> tuple[Vendor, Product, Doc]:
    unique = uuid.uuid4().hex[:6]
    v = Vendor(
        id=uuid.uuid4(),
        name=f"Acme-{unique}",
        slug=f"acme-{unique}",
        status="active",
    )
    db_session.add(v)
    await db_session.flush()
    p = Product(
        id=uuid.uuid4(),
        vendor_id=v.id,
        name="FW",
        slug=f"fw-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db_session.add(p)
    await db_session.flush()
    d = Doc(
        id=uuid.uuid4(),
        vendor_id=v.id,
        content="# example",
        content_format="markdown",
        fetched_at=datetime.now(UTC),
        fetched_by="manual",
    )
    db_session.add(d)
    await db_session.flush()
    await db_session.commit()
    return v, p, d


def _make_svc(
    session_factory: async_sessionmaker[AsyncSession],
    anthropic: Any,
    *,
    vrl_validator: Any = _noop_validator,
) -> LlmDraftService:
    return LlmDraftService(
        session_factory=session_factory,
        anthropic_client=anthropic,
        model="claude-opus-4-7",
        job_repo=LlmGenerationJobRepository(session_factory),
        vrl_validator=vrl_validator,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestGenerateDraftHappy:
    async def test_writes_three_tables_and_finishes_job(
        self, db_session, db_session_factory,
    ):
        _, p, d = await _seed_minimal(db_session)
        anthropic = _FakeAnthropic(_fake_anthropic_response(_good_tool_input()))
        svc = _make_svc(db_session_factory, anthropic)

        result = await svc.generate_draft(
            doc_id=d.id, product_id=p.id,
            requested_by=None, hint=None,
        )

        async with db_session_factory() as s:
            lt = await s.get(LogType, result.log_type_id)
            assert lt is not None
            assert lt.status == "llm_draft"
            assert lt.source == "llm_generated"
            assert lt.source_job_id == result.job_id

            pr = await s.get(ParseRule, result.parse_rule_id)
            assert pr is not None
            assert pr.status == "llm_draft"
            assert pr.source == "llm_generated"
            assert pr.source_job_id == result.job_id

            res = await s.execute(
                select(FieldSchema).where(FieldSchema.log_type_id == lt.id)
            )
            assert len(res.scalars().all()) == 1

            job = await s.get(LlmGenerationJob, result.job_id)
            assert job is not None
            assert job.status == "succeeded"
            assert job.input_tokens == 100
            assert job.output_tokens == 50
            assert job.cache_read_tokens == 10
            assert job.log_type_id == result.log_type_id
            assert job.parse_rule_id == result.parse_rule_id


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


class TestGenerateDraftFailures:
    async def test_schema_mismatch_records_failed_job(
        self, db_session, db_session_factory,
    ):
        _, p, d = await _seed_minimal(db_session)
        # Anthropic response with NO tool_use blocks → SchemaMismatchError.
        bad_resp = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hello")],
            stop_reason="end_turn",
            usage=SimpleNamespace(
                input_tokens=10, output_tokens=5, cache_read_input_tokens=0,
            ),
            model_dump=lambda: {"id": "x"},
        )
        anthropic = _FakeAnthropic(bad_resp)
        svc = _make_svc(db_session_factory, anthropic)

        with pytest.raises(SchemaMismatchError) as exc_info:
            await svc.generate_draft(
                doc_id=d.id, product_id=p.id,
                requested_by=None, hint=None,
            )
        # Exception carries job_id side-channel for the router.
        assert getattr(exc_info.value, "job_id", None) is not None

        async with db_session_factory() as s:
            res = await s.execute(
                select(LlmGenerationJob).where(LlmGenerationJob.product_id == p.id)
            )
            jobs = res.scalars().all()
            assert len(jobs) == 1
            job = jobs[0]
            assert job.status == "failed"
            assert job.error_code == "schema_mismatch"
            assert job.raw_response is not None  # serialized fake response
            # No library row should have leaked.
            r = await s.execute(select(LogType).where(LogType.product_id == p.id))
            assert r.scalars().all() == []

    async def test_vrl_compile_failed_records_failed_job(
        self, db_session, db_session_factory,
    ):
        _, p, d = await _seed_minimal(db_session)
        anthropic = _FakeAnthropic(_fake_anthropic_response(_good_tool_input()))

        def bad_validator(code: str, *, engine_version: str) -> None:
            raise VrlCompileError("compile bomb")

        svc = _make_svc(db_session_factory, anthropic, vrl_validator=bad_validator)

        with pytest.raises(VrlCompileError):
            await svc.generate_draft(
                doc_id=d.id, product_id=p.id,
                requested_by=None, hint=None,
            )

        async with db_session_factory() as s:
            res = await s.execute(
                select(LlmGenerationJob).where(LlmGenerationJob.product_id == p.id)
            )
            jobs = res.scalars().all()
            assert len(jobs) == 1
            assert jobs[0].error_code == "vrl_compile_failed"
            # Verify NO library row leaked (write happens after vrl validation).
            r = await s.execute(select(LogType).where(LogType.product_id == p.id))
            assert r.scalars().all() == []

    async def test_anthropic_failure_records_failed_job(
        self, db_session, db_session_factory,
    ):
        _, p, d = await _seed_minimal(db_session)
        boom = _FakeAnthropic(RuntimeError("api 500"))
        svc = _make_svc(db_session_factory, boom)

        with pytest.raises(AnthropicCallError):
            await svc.generate_draft(
                doc_id=d.id, product_id=p.id,
                requested_by=None, hint=None,
            )

        async with db_session_factory() as s:
            res = await s.execute(
                select(LlmGenerationJob).where(LlmGenerationJob.product_id == p.id)
            )
            jobs = res.scalars().all()
            assert len(jobs) == 1
            job = jobs[0]
            assert job.error_code == "anthropic_failed"
            # Anthropic never returned a response → raw_response stays NULL.
            assert job.raw_response is None

    async def test_doc_not_found_raises_404(self, db_session_factory):
        anthropic = _FakeAnthropic(_fake_anthropic_response(_good_tool_input()))
        svc = _make_svc(db_session_factory, anthropic)

        ghost_doc_id = uuid.uuid4()
        ghost_product_id = uuid.uuid4()
        with pytest.raises(NotFoundError):
            await svc.generate_draft(
                doc_id=ghost_doc_id, product_id=ghost_product_id,
                requested_by=None, hint=None,
            )

        # Pre-flight failed BEFORE TX-1, so no job row should exist for these
        # synthetic ids (other tests' rows are scoped to their own ids).
        async with db_session_factory() as s:
            res = await s.execute(
                select(LlmGenerationJob).where(
                    LlmGenerationJob.doc_id == ghost_doc_id,
                )
            )
            assert res.scalars().all() == []
