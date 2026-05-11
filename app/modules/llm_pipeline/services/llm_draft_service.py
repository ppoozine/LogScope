"""Orchestrates LLM draft generation per spec §3.4.

Responsible for:
- creating a pending job (TX-1)
- calling Anthropic
- parsing tool_use + self-consistency check + VRL compile
- writing log_type / fields / parse_rule + finishing job as succeeded (TX-2)
- on any failure, finishing job as failed in independent transaction (TX-3)
"""
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.exceptions import NotFoundError
from app.common.utils.slug import slugify
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.repositories.field_schema_repository import (
    FieldSchemaRepository,
)
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.llm_pipeline.exceptions import (
    AnthropicCallError,
    DbWriteError,
    LlmDraftError,
)
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository
from app.modules.llm_pipeline.repositories.llm_generation_job_repository import (
    LlmGenerationJobRepository,
)
from app.modules.llm_pipeline.services.prompt_builder import (
    DRAFT_TOOL_SCHEMA,
    DraftPromptContext,
    ExistingLogTypeView,
    FieldView,
    build_system_blocks,
)
from app.modules.llm_pipeline.services.tool_use_parser import (
    DraftPayload,
    check_self_consistency,
    parse_tool_use,
)

_RAW_RESPONSE_MAX = 4096


@dataclass(frozen=True)
class GenerationResult:
    job_id: uuid.UUID
    log_type_id: uuid.UUID
    parse_rule_id: uuid.UUID


def _truncate_response(text: str | None, limit: int = _RAW_RESPONSE_MAX) -> str | None:
    if text is None:
        return None
    return text[:limit]


def _serialize_response(response: Any) -> str:
    """Best-effort serialize an Anthropic response for audit storage."""
    try:
        if hasattr(response, "model_dump"):
            return json.dumps(response.model_dump(), default=str)
        if hasattr(response, "to_dict"):
            return json.dumps(response.to_dict(), default=str)
    except Exception:
        pass
    return str(response)


class LlmDraftService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        anthropic_client: Any,
        model: str,
        job_repo: LlmGenerationJobRepository,
        vrl_validator: Any,  # callable(vrl_code, *, engine_version) -> None
    ) -> None:
        self._session_factory = session_factory
        self._anthropic = anthropic_client
        self._model = model
        self._job_repo = job_repo
        self._vrl_validator = vrl_validator

    async def generate_draft(
        self,
        *,
        doc_id: uuid.UUID,
        product_id: uuid.UUID,
        requested_by: uuid.UUID | None,
        hint: str | None,
    ) -> GenerationResult:
        # Pre-flight reads (own session)
        async with self._session_factory() as session:
            doc_repo = DocRepository(session)
            doc = await doc_repo.get_by_id(doc_id)
            if doc is None:
                raise NotFoundError("doc not found")
            product_repo = ProductRepository(session)
            product = await product_repo.get_by_id(product_id)
            if product is None:
                raise NotFoundError("product not found")
            vendor_repo = VendorRepository(session)
            vendor = await vendor_repo.get_by_id(product.vendor_id)
            assert vendor is not None  # FK guarantees this
            log_type_repo = LogTypeRepository(session)
            field_schema_repo = FieldSchemaRepository(session)
            existing = await log_type_repo.list_by_product(product_id)
            existing_views: list[ExistingLogTypeView] = []
            for elt in existing:
                fields = await field_schema_repo.list_by_log_type(elt.id)
                existing_views.append(
                    ExistingLogTypeView(
                        name=elt.name,
                        format=elt.format,
                        transport=elt.transport,
                        fields=[
                            FieldView(
                                name=f.field_name,
                                type=f.field_type,
                                required=f.is_required,
                            )
                            for f in fields
                        ],
                    )
                )

            ctx = DraftPromptContext(
                vendor_name=vendor.name,
                vendor_slug=vendor.slug,
                product_name=product.name,
                product_slug=product.slug,
                product_version=product.version,
                product_deploy_type=product.deploy_type,
                existing_log_types=existing_views,
                doc_title=doc.title,
                doc_url=doc.url,
                doc_content=doc.content,
                hint=hint,
            )

        # TX-1: pending job (own session, commits independently)
        job_id = await self._job_repo.create_pending(
            doc_id=doc_id,
            product_id=product_id,
            requested_by=requested_by,
            model=self._model,
        )

        response: Any = None
        try:
            system_blocks = build_system_blocks(ctx)
            try:
                response = await self._anthropic.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    system=system_blocks,
                    messages=[{"role": "user", "content": "Generate draft."}],
                    tools=[DRAFT_TOOL_SCHEMA],
                    tool_choice={"type": "tool", "name": "submit_draft"},
                )
            except Exception as e:
                raise AnthropicCallError(str(e)) from e

            draft = parse_tool_use(response)
            check_self_consistency(draft)
            self._vrl_validator(draft.vrl_code, engine_version=draft.engine_version)

            # TX-2: library writes + job.finish_succeeded
            log_type_id, parse_rule_id = await self._write_drafts(
                product_id=product_id, draft=draft, job_id=job_id,
            )
            usage = getattr(response, "usage", None)
            await self._job_repo.finish_succeeded(
                job_id,
                log_type_id=log_type_id,
                parse_rule_id=parse_rule_id,
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
            )
            return GenerationResult(
                job_id=job_id,
                log_type_id=log_type_id,
                parse_rule_id=parse_rule_id,
            )

        except LlmDraftError as e:
            # TX-3: independent failed write
            await self._job_repo.finish_failed(
                job_id,
                error_code=e.error_code,
                error_message=str(e),
                raw_response=(
                    _truncate_response(_serialize_response(response))
                    if response is not None
                    else None
                ),
            )
            e.job_id = job_id  # type: ignore[attr-defined]  # consumed by router
            raise

    async def _write_drafts(
        self,
        *,
        product_id: uuid.UUID,
        draft: DraftPayload,
        job_id: uuid.UUID,
    ) -> tuple[uuid.UUID, uuid.UUID]:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    lt = LogType(
                        id=uuid.uuid4(),
                        product_id=product_id,
                        name=draft.log_type.name,
                        slug=slugify(draft.log_type.name),
                        format=draft.log_type.format,
                        transport=draft.log_type.transport,
                        status="llm_draft",
                        source="llm_generated",
                        source_job_id=job_id,
                        description=draft.log_type.description,
                    )
                    session.add(lt)
                    await session.flush()

                    fs_repo = FieldSchemaRepository(session)
                    field_rows = [
                        FieldSchema(
                            id=uuid.uuid4(),
                            log_type_id=lt.id,
                            field_name=f.field_name,
                            field_type=f.field_type,
                            description=f.description,
                            is_required=f.is_required,
                            is_identifier=f.is_identifier,
                            example_value=f.example_value,
                            sort_order=i,
                        )
                        for i, f in enumerate(draft.fields)
                    ]
                    await fs_repo.replace_for_log_type(lt.id, field_rows)

                    pr = ParseRule(
                        id=uuid.uuid4(),
                        log_type_id=lt.id,
                        version=1,
                        vrl_code=draft.vrl_code,
                        engine_version=draft.engine_version,
                        status="llm_draft",
                        source="llm_generated",
                        source_job_id=job_id,
                        notes=draft.notes,
                    )
                    session.add(pr)
                    await session.flush()
                    return lt.id, pr.id
        except Exception as e:
            raise DbWriteError(f"library write failed: {type(e).__name__}: {e}") from e
