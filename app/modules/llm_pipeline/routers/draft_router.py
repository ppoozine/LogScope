"""POST /api/v1/llm-pipeline/drafts/generate."""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.config import Settings, get_settings
from app.core.database import get_db_sessionmaker
from app.core.deps import get_anthropic_client
from app.modules.auth.models.user import User
from app.modules.llm_pipeline.exceptions import LlmDraftError
from app.modules.llm_pipeline.repositories.llm_generation_job_repository import (
    LlmGenerationJobRepository,
)
from app.modules.llm_pipeline.routers.throttle import (
    InMemoryThrottle,
    ThrottleExceeded,
    get_throttle,
)
from app.modules.llm_pipeline.schemas import (
    GenerateDraftErrorPayload,
    GenerateDraftRequest,
    GenerateDraftResponse,
)
from app.modules.llm_pipeline.services.llm_draft_service import LlmDraftService
from app.modules.llm_pipeline.services.vrl_validator import validate_vrl

router = APIRouter()


_HTTP_FOR_CODE: dict[str, int] = {
    "schema_mismatch":      422,
    "vrl_fields_disjoint":  422,
    "vrl_compile_failed":   422,
    "anthropic_failed":     502,
    "db_write_failed":      500,
}


def get_draft_service(
    settings: Annotated[Settings, Depends(get_settings)],
    anthropic_client: Annotated[Any, Depends(get_anthropic_client)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_db_sessionmaker)
    ],
) -> LlmDraftService:
    return LlmDraftService(
        session_factory=session_factory,
        anthropic_client=anthropic_client,
        model=settings.llm_pipeline_draft_model,
        job_repo=LlmGenerationJobRepository(session_factory),
        vrl_validator=validate_vrl,
    )


@router.post(
    "/drafts/generate",
    response_model=DataResponse[GenerateDraftResponse],
)
async def generate_draft(
    body: GenerateDraftRequest,
    service: Annotated[LlmDraftService, Depends(get_draft_service)],
    throttle: Annotated[InMemoryThrottle, Depends(get_throttle)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[GenerateDraftResponse]:
    try:
        throttle.check(user.id)
    except ThrottleExceeded as e:
        raise HTTPException(status_code=429, detail=str(e)) from e

    try:
        result = await service.generate_draft(
            doc_id=body.doc_id,
            product_id=body.product_id,
            requested_by=user.id,
            hint=body.hint,
        )
    except LlmDraftError as e:
        http = _HTTP_FOR_CODE.get(e.error_code, 500)
        # job_id was attached as a side-channel by LlmDraftService (M10)
        job_id = getattr(e, "job_id", None) or uuid.UUID(
            "00000000-0000-0000-0000-000000000000"
        )
        raise HTTPException(
            status_code=http,
            detail=GenerateDraftErrorPayload(
                job_id=job_id,
                error_code=e.error_code,
                error_message=str(e),
            ).model_dump(mode="json"),
        ) from e

    return DataResponse(
        data=GenerateDraftResponse(
            job_id=result.job_id,
            log_type_id=result.log_type_id,
            parse_rule_id=result.parse_rule_id,
        )
    )
