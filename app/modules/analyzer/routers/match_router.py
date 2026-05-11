"""POST /api/v1/analyzer/match — LLM-based vendor/product matching."""

from typing import Annotated, Any, cast

import anthropic
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.deps import get_anthropic_client
from app.modules.analyzer.repositories.catalog_repository import CatalogRepository
from app.modules.analyzer.schemas import MatchRequest, MatchResponse
from app.modules.analyzer.services.match_service import MatchService
from app.modules.auth.models.user import User

router = APIRouter()


async def get_match_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[anthropic.AsyncAnthropic, Depends(get_anthropic_client)],
) -> MatchService:
    """Construct MatchService from DI dependencies.

    Service short-circuits to empty candidates when ``anthropic_api_key`` is
    unset, so the placeholder client is never actually called.
    """
    return MatchService(
        catalog_repo=CatalogRepository(session),
        anthropic_client=cast(Any, client),
        anthropic_api_key=settings.anthropic_api_key,
        model=settings.llm_match_model,
    )


@router.post("/match", response_model=DataResponse[MatchResponse])
async def match(
    body: MatchRequest,
    service: Annotated[MatchService, Depends(get_match_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[MatchResponse]:
    response = await service.match(raw_log=body.raw_log, top_k=body.top_k)
    return DataResponse(data=response)
